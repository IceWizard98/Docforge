"""Per-slot targeted retrieval.

For a given document type, runs one targeted corpus query per information slot
(scoped by doc_type) and reports each slot as filled / missing / ambiguous with
its supporting evidence. This is the "no blind dump" core: retrieval is driven by
the slot's query hint, and only confidently-matched slots count as filled.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal

from core.services.context import ContextChunk, ContextPackService
from core.services.scoring import Bucket, bucket
from core.services.search import RetrievalFilters
from core.services.slot_schema import SlotSchemaService

logger = logging.getLogger(__name__)

SlotFillStatus = Literal["filled", "missing", "ambiguous"]

# Two near-tied top chunks from different sources => ambiguous evidence.
_AMBIGUITY_MARGIN = 0.15


@dataclass
class SlotFill:
    slot_id: str
    label: str
    status: SlotFillStatus
    chunks: list[ContextChunk] = field(default_factory=list)
    confidence_bucket: Bucket = "low"
    best_confidence: float = 0.0


@dataclass
class SlotContextPack:
    doc_type: str
    slots: list[SlotFill] = field(default_factory=list)
    total_tokens: int = 0


class SlotRetrievalService:
    MAX_TOKENS = 4000

    def __init__(
        self,
        context_service: ContextPackService | None = None,
        slot_service: SlotSchemaService | None = None,
        pgvector=None,
        llm_provider=None,
    ):
        if context_service is not None:
            self._ctx = context_service
        else:
            self._ctx = ContextPackService(pgvector=pgvector, llm_provider=llm_provider)
        self._slots = slot_service or SlotSchemaService()

    async def build_slot_context(
        self, doc_type: str, top_k: int = 3
    ) -> SlotContextPack:
        schema = self._slots.get(doc_type)
        if schema is None:
            return SlotContextPack(doc_type=doc_type)

        filters = RetrievalFilters(doc_type=[doc_type])

        # Pass 1 — retrieve per slot (isolated failures => empty).
        retrieved: dict[str, list[ContextChunk]] = {}
        for slot in schema.slots:
            query = slot.retrieval_query_hint or slot.label
            try:
                pack = await self._ctx.build_section_context(
                    section_title=query, filters=filters, top_k=top_k
                )
                chunks = [c for src in pack.sources for c in src.chunks]
            except Exception:
                logger.exception("Slot retrieval failed for %s/%s", doc_type, slot.id)
                chunks = []
            chunks.sort(key=lambda c: c.relevance_score, reverse=True)
            retrieved[slot.id] = chunks

        global_max = max(
            (c.relevance_score for chunks in retrieved.values() for c in chunks),
            default=0.0,
        )

        # Pass 2 — classify + attach evidence under a shared token budget.
        slots: list[SlotFill] = []
        total_tokens = 0
        for slot in schema.slots:
            chunks = retrieved[slot.id]
            fill = self._classify_slot(slot.id, slot.label, chunks, global_max)
            # Attach evidence within the remaining budget.
            attached: list[ContextChunk] = []
            for c in chunks:
                tokens = max(1, len(c.content) // 4)
                if total_tokens + tokens > self.MAX_TOKENS:
                    break
                attached.append(c)
                total_tokens += tokens
            fill.chunks = attached
            slots.append(fill)

        return SlotContextPack(doc_type=doc_type, slots=slots, total_tokens=total_tokens)

    def _classify_slot(
        self, slot_id: str, label: str, chunks: list[ContextChunk], global_max: float
    ) -> SlotFill:
        if not chunks or global_max <= 0:
            return SlotFill(slot_id=slot_id, label=label, status="missing")

        rel = chunks[0].relevance_score / global_max
        b = bucket(rel)
        if b == "high":
            status: SlotFillStatus = "filled"
        elif b == "medium":
            status = "ambiguous"
        else:
            status = "missing"

        # Conflicting top evidence from different sources => ambiguous.
        if status == "filled" and len(chunks) >= 2:
            top, second = chunks[0], chunks[1]
            if top.source_doc_id != second.source_doc_id and top.relevance_score > 0:
                margin = (top.relevance_score - second.relevance_score) / top.relevance_score
                if margin < _AMBIGUITY_MARGIN:
                    status = "ambiguous"

        return SlotFill(
            slot_id=slot_id,
            label=label,
            status=status,
            confidence_bucket=b,
            best_confidence=round(rel, 4),
        )
