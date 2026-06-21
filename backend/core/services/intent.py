"""Draft intent inference.

Given a conversation (and optionally a preview of the open document), infer which
document the user is drafting and of what type, then assess — per the type's slot
schema — which required pieces of information are known, missing or ambiguous.

Transparency-first: never invents a type; if it cannot tell, ``doc_type`` is None.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal

from core.services.slot_schema import SlotSchemaService
from ports.llm import LLMProvider

logger = logging.getLogger(__name__)

SlotStatus = Literal["known", "missing", "ambiguous"]

INTENT_PROMPT_TEMPLATE = """You analyze a drafting conversation to infer intent.

Allowed document types (choose EXACTLY one, or null if unclear): {doc_types}

If a type is chosen, here are its information slots:
{slots}

Conversation:
{conversation}

Return a JSON object:
- "doc_type": one of the allowed types, or null if you cannot tell
- "doc_type_confidence": float 0..1
- "title_guess": a concise document title, or ""
- "slots": array of {{"slot_id": "...", "status": "known"|"missing"|"ambiguous",
  "value_summary": "what the user said, if known"}}
Mark a slot "known" only if the conversation actually provides that information.
Respond with valid JSON only."""


@dataclass
class SlotState:
    slot_id: str
    status: SlotStatus
    value_summary: str = ""
    source: Literal["conversation", "none"] = "none"


@dataclass
class DraftIntent:
    doc_type: str | None = None
    doc_type_confidence: float = 0.0
    title_guess: str = ""
    slots: list[SlotState] = field(default_factory=list)
    reasoning: str = ""


class IntentInferenceService:
    def __init__(
        self,
        llm: LLMProvider | None = None,
        slot_service: SlotSchemaService | None = None,
    ):
        self._llm = llm
        self._slots = slot_service or SlotSchemaService()

    def detect_doc_type(self, text: str) -> str | None:
        """Cheap deterministic alias match over free-form text (no LLM)."""
        if not isinstance(text, str) or not text.strip():
            return None
        low = text.lower()
        for alias, doc_type in self._alias_pairs():
            if alias in low:
                return doc_type
        return None

    def _deterministic_doc_type(self, messages: list[dict]) -> str | None:
        """Cheap alias match over the conversation text."""
        text = " ".join(
            str(m.get("content", "")) for m in messages if isinstance(m, dict)
        )
        return self.detect_doc_type(text)

    def _alias_pairs(self) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        for dt in self._slots.list_doc_types():
            schema = self._slots.get(dt)
            if not schema:
                continue
            pairs.append((dt.lower(), dt))
            pairs.extend((a.lower(), dt) for a in schema.aliases)
        # Longer aliases first so "non-disclosure" wins over a bare substring.
        pairs.sort(key=lambda p: len(p[0]), reverse=True)
        return pairs

    def _all_slots_missing(self, doc_type: str) -> list[SlotState]:
        schema = self._slots.get(doc_type)
        if not schema:
            return []
        return [SlotState(slot_id=s.id, status="missing") for s in schema.slots]

    async def infer(
        self,
        messages: list[dict],
        doc_preview: str = "",
        llm: LLMProvider | None = None,
    ) -> DraftIntent:
        provider = llm or self._llm
        deterministic = self._deterministic_doc_type(messages)

        if provider is None:
            if deterministic:
                return DraftIntent(
                    doc_type=deterministic,
                    doc_type_confidence=0.5,
                    slots=self._all_slots_missing(deterministic),
                    reasoning="Tipo dedotto da parole chiave nella conversazione.",
                )
            return DraftIntent()

        conversation = "\n".join(
            f"{m.get('role', 'user')}: {str(m.get('content', ''))[:500]}"
            for m in messages if isinstance(m, dict)
        )
        if doc_preview:
            conversation += f"\n\n[Documento aperto]\n{doc_preview[:1000]}"

        prompt = INTENT_PROMPT_TEMPLATE.format(
            doc_types=", ".join(self._slots.list_doc_types()),
            slots=self._format_slots_hint(),
            conversation=conversation or "(vuota)",
        )
        try:
            result = await provider.generate_structured(prompt, dict)
        except Exception:
            logger.exception("Intent inference LLM call failed")
            if deterministic:
                return DraftIntent(
                    doc_type=deterministic,
                    doc_type_confidence=0.5,
                    slots=self._all_slots_missing(deterministic),
                    reasoning="Fallback: tipo dedotto da parole chiave.",
                )
            return DraftIntent()

        return self._build_intent(result, deterministic)

    def _format_slots_hint(self) -> str:
        lines: list[str] = []
        for dt in self._slots.list_doc_types():
            schema = self._slots.get(dt)
            if not schema:
                continue
            slot_ids = ", ".join(s.id for s in schema.slots)
            lines.append(f"- {dt}: {slot_ids}")
        return "\n".join(lines)

    def _build_intent(self, result: dict, deterministic: str | None) -> DraftIntent:
        raw_type = result.get("doc_type")
        valid = set(self._slots.list_doc_types())
        if raw_type in valid:
            doc_type = raw_type
        elif deterministic in valid:
            doc_type = deterministic
        else:
            doc_type = None
        if doc_type is None:
            return DraftIntent(reasoning=str(result.get("reasoning", "")))

        schema = self._slots.get(doc_type)
        schema_ids = [s.id for s in schema.slots] if schema else []
        returned: dict[str, dict] = {}
        for entry in result.get("slots") or []:
            if isinstance(entry, dict) and entry.get("slot_id"):
                returned[str(entry["slot_id"])] = entry

        slots: list[SlotState] = []
        for sid in schema_ids:
            entry = returned.get(sid)
            if entry:
                status = entry.get("status")
                status = status if status in ("known", "missing", "ambiguous") else "missing"
                slots.append(SlotState(
                    slot_id=sid,
                    status=status,
                    value_summary=str(entry.get("value_summary", "")),
                    source="conversation" if status == "known" else "none",
                ))
            else:
                slots.append(SlotState(slot_id=sid, status="missing"))

        try:
            confidence = float(result.get("doc_type_confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0

        return DraftIntent(
            doc_type=doc_type,
            doc_type_confidence=confidence,
            title_guess=str(result.get("title_guess", "")),
            slots=slots,
            reasoning=str(result.get("reasoning", "")),
        )
