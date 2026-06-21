import logging
from dataclasses import dataclass, field
from uuid import uuid4

from ports.llm import LLMProvider

logger = logging.getLogger(__name__)


@dataclass
class DocumentSpec:
    draft_id: str = ""
    chat_session_id: str = ""
    title: str = ""
    sections: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class DraftSection:
    section_id: str = ""
    title: str = ""
    content: str = ""
    status: str = "draft"
    provenance: list[dict] = field(default_factory=list)


SPEC_PROMPT_TEMPLATE = """Analyze the following chat messages and produce a document spec outline.

Chat messages:
{messages}

Return a JSON object with:
- "title": a concise document title
- "sections": array of {{"section_id": "slug", "title": "..."}}

Respond with valid JSON only."""

SECTION_PROMPT_TEMPLATE = """Write content for the document section based on spec and context.

Document title: {title}
Section title: {section_title}
Section ID: {section_id}

Ecco il contesto dai documenti sorgente:
{context_pack}

REGOLA ANTI-ALLUCINAZIONE (vincolante): ogni affermazione deve essere
riconducibile al contesto sorgente. NON inventare fatti, clausole, nomi, importi
o date non presenti nel contesto. Se un'informazione non è nelle fonti, NON
scriverla come se fosse certa: marcala esplicitamente come segnaposto.

Ogni chunk nel contesto è preceduto da [source_doc_id=... chunk_id=...]: usa
ESATTAMENTE quei valori quando citi una fonte (mai inventarli).

Write the section in a professional, clear style, split into runs.
Return a JSON object with:
- "content": the full section text (concatenation of the runs' text)
- "provenance": array of {{"source_doc_id":"...","chunk_id":"...","confidence":<float>}}
  for sourced parts (i valori presi dalle etichette del contesto)
- "runs": array of spans, each {{"text": "...",
    "provenance": {{"source_doc_id":"...","chunk_id":"...","confidence":<float>}} | null,
    "placeholder": {{"slot_id":"...","reason":"..."}} | null }}
  A run is EITHER sourced (provenance set, placeholder null) OR a placeholder
  (placeholder set, provenance null) for information not found in the sources.
- "placeholders": array of {{"slot_id":"...","reason":"..."}} for missing info

Respond with valid JSON only."""


class DraftService:
    def __init__(
        self,
        llm: LLMProvider | None = None,
        context_service: object | None = None,
    ):
        self._llm = llm
        self._context_service = context_service

    async def generate_spec(
        self, chat_session_id: str, messages: list[dict], llm: LLMProvider | None = None
    ) -> dict:
        provider = llm or self._llm
        if provider:
            last_message = messages[-1]["content"] if messages else ""
            prompt = SPEC_PROMPT_TEMPLATE.format(
                messages=last_message[:3000] if last_message else "(no messages)"
            )
            try:
                result = await provider.generate_structured(prompt, dict)
                return {
                    "draft_id": f"draft_{uuid4().hex[:8]}",
                    "chat_session_id": chat_session_id,
                    "title": result.get("title", f"Draft from chat {chat_session_id[:8]}"),
                    "sections": result.get("sections", []),
                    "metadata": {
                        "source": "chat",
                        "message_count": len(messages),
                        "intent": last_message[:200] if last_message else "",
                    },
                }
            except Exception:
                logger.exception("LLM spec generation failed for session %s", chat_session_id)
        spec = {
            "draft_id": f"draft_{uuid4().hex[:8]}",
            "chat_session_id": chat_session_id,
            "title": "Generated Document",
            "sections": [],
            "metadata": {},
        }
        last_message = messages[-1]["content"] if messages else ""
        spec["title"] = f"Draft from chat {chat_session_id[:8]}"
        spec["metadata"]["source"] = "chat"
        spec["metadata"]["message_count"] = len(messages)
        spec["metadata"]["intent"] = last_message[:200] if last_message else ""
        return spec

    async def generate_section(
        self,
        spec: dict,
        section: dict,
        context_pack: object | None = None,
        llm: LLMProvider | None = None,
        context_service: object | None = None,
    ) -> dict:
        provider = llm or self._llm
        ctx_svc = context_service or self._context_service
        section_id = section.get("section_id", f"sec_{uuid4().hex[:8]}")

        if context_pack is None:
            from core.services.context import ContextPack

            context_pack = ContextPack()

        if ctx_svc is not None and not self._has_context(context_pack):
            context_pack = await ctx_svc.build_section_context(
                document_id=spec.get("document_id", ""),
                section_title=section.get("title", ""),
                section_id=section_id,
            )

        if provider:
            context_text = self._format_context_pack(context_pack, ctx_svc)
            prompt = SECTION_PROMPT_TEMPLATE.format(
                title=spec.get("title", ""),
                section_title=section.get("title", ""),
                section_id=section_id,
                context_pack=context_text or "(no context available)",
            )
            try:
                result = await provider.generate_structured(prompt, dict)
                content = result.get("content", "")
                provenance_raw = result.get("provenance", [])
                provenance = self._build_provenance(provenance_raw, context_pack)
                runs = self._build_runs(result, content, provenance)
                return {
                    "section_id": section_id,
                    "title": section.get("title", ""),
                    "content": content,
                    "status": "draft",
                    "provenance": provenance,
                    "runs": runs,
                    "placeholders": [r["placeholder"] for r in runs if r["placeholder"]],
                }
            except Exception:
                logger.exception(
                    "LLM section generation failed for %s/%s",
                    spec.get("draft_id", ""),
                    section_id,
                )
        return {
            "section_id": section_id,
            "title": section.get("title", ""),
            "content": "",
            "status": "draft",
            "provenance": self._build_provenance([], context_pack),
            "runs": [],
            "placeholders": [],
        }

    async def compose_context_pack(
        self, document_id: str, section_id: str, retrieved_chunks: list[dict]
    ):
        from core.services.context import ContextChunk, ContextPack, ContextSource

        if not retrieved_chunks:
            return ContextPack()

        doc_chunks = []
        for chunk in retrieved_chunks:
            doc_chunks.append(
                ContextChunk(
                    chunk_id=chunk.get("id", chunk.get("chunk_id", "")),
                    content=chunk.get("text", chunk.get("content", "")),
                    source_doc_id=chunk.get("document_id", document_id),
                )
            )
        return ContextPack(
            sources=[ContextSource(doc_id=document_id, chunks=doc_chunks)],
            total_tokens=len(doc_chunks),
        )

    def _format_context_pack(self, pack, ctx_svc=None) -> str:
        # Expose the real source_doc_id + chunk_id alongside each chunk so the LLM
        # can cite them verbatim in provenance/runs; a title-only context (as
        # build_prompt_context produces) leaves provenance unresolvable.
        parts = []
        try:
            for source in pack.sources:
                for chunk in source.chunks:
                    parts.append(
                        f"[source_doc_id={chunk.source_doc_id} chunk_id={chunk.chunk_id}] "
                        f"{chunk.content[:500]}"
                    )
        except AttributeError:
            pass
        return "\n".join(parts)

    def _build_runs(self, result: dict, content: str, provenance: list[dict]) -> list[dict]:
        """Normalize per-span runs, synthesizing a safe default when absent.

        Each run is either sourced (provenance set) or a placeholder. When the LLM
        returns no runs, unsourced content is conservatively flagged as a
        placeholder rather than passed off as sourced (anti-hallucination).
        """
        raw_runs = result.get("runs")
        if isinstance(raw_runs, list) and raw_runs:
            runs: list[dict] = []
            for r in raw_runs:
                if not isinstance(r, dict):
                    continue
                prov = r.get("provenance") if isinstance(r.get("provenance"), dict) else None
                ph = r.get("placeholder") if isinstance(r.get("placeholder"), dict) else None
                runs.append({
                    "text": str(r.get("text", "")),
                    "provenance": prov,
                    "placeholder": ph,
                })
            if runs:
                return runs

        if not content:
            return []
        if provenance:
            first = provenance[0]
            return [{
                "text": content,
                "provenance": {
                    "source": first.get("source", ""),
                    "chunk_id": first.get("chunk_id", ""),
                    "confidence": first.get("confidence", 0.0),
                },
                "placeholder": None,
            }]
        # Unsourced content -> placeholder, never silently "sourced".
        return [{
            "text": content,
            "provenance": None,
            "placeholder": {"slot_id": "", "reason": "Contenuto non riconducibile a una fonte"},
        }]

    def _build_provenance(self, raw: list[dict], pack) -> list[dict]:
        if not raw:
            return _fallback_provenance(pack)
        fb_doc, fb_chunk = _first_chunk_ids(pack)
        result = []
        for p in raw[:5]:
            src = p.get("source_doc_id") or p.get("source", "")
            chunk_id, source_doc_id = _resolve_chunk(src, pack)
            chunk_id = p.get("chunk_id") or chunk_id
            source_doc_id = p.get("source_doc_id") or source_doc_id
            # Guarantee a real source-document id when context exists, so the LLM
            # echoing an unresolvable free-form "source" still yields a provenance
            # row that satisfies the promote-time NOT NULL FK.
            if not source_doc_id and fb_doc:
                source_doc_id = fb_doc
                chunk_id = chunk_id or fb_chunk
            result.append({
                "source": p.get("source", source_doc_id),
                "source_doc_id": source_doc_id,
                "confidence": p.get("confidence", 0.0),
                "chunk_id": chunk_id,
            })
        return result

    def _has_context(self, pack) -> bool:
        try:
            return bool(pack.sources)
        except AttributeError:
            return False


def _runs_to_inline(runs: list) -> list[dict]:
    """Generated per-span runs -> ProseMirror inline text nodes with marks.

    Sourced runs carry the 'provenance' mark; unsourced runs 'placeholderMark',
    so a hallucinated span can never look grounded. Shared by the chat draft
    action and the async draft worker.
    """
    nodes: list[dict] = []
    for r in runs or []:
        if not isinstance(r, dict):
            continue
        text = r.get("text", "")
        if not text:
            continue
        node: dict = {"type": "text", "text": text}
        prov = r.get("provenance") if isinstance(r.get("provenance"), dict) else None
        ph = r.get("placeholder") if isinstance(r.get("placeholder"), dict) else None
        if prov:
            node["marks"] = [{"type": "provenance", "attrs": {
                "sourceDocId": prov.get("source_doc_id") or prov.get("source", ""),
                "chunkId": prov.get("chunk_id"),
                "confidence": prov.get("confidence", 0),
            }}]
        elif ph:
            node["marks"] = [{"type": "placeholderMark", "attrs": {
                "slotId": ph.get("slot_id"),
                "reason": ph.get("reason"),
            }}]
        nodes.append(node)
    return nodes


def build_section_paragraph(sec: dict) -> dict:
    """A section's paragraph node, applying per-span marks when runs exist."""
    runs = sec.get("runs")
    if isinstance(runs, list) and runs:
        return {"type": "paragraph", "content": _runs_to_inline(runs)}
    content = sec.get("content", "")
    inline = [{"type": "text", "text": content}] if content else []
    return {"type": "paragraph", "content": inline}


def build_section_node(sec: dict, index: int) -> dict:
    """A top-level ProseMirror section node from a generated section result."""
    section_id = sec.get("section_id") or f"sec_{uuid4().hex[:8]}"
    return {
        "type": "section",
        "attrs": {
            "sectionId": section_id,
            "title": sec.get("title", f"Sezione {index + 1}"),
            "number": index + 1,
            "status": sec.get("status", "draft"),
        },
        "content": [build_section_paragraph(sec)],
    }


def assemble_draft_content(section_results: list[dict]) -> dict:
    """Build the full ProseMirror doc from generated section results."""
    return {
        "type": "doc",
        "content": [build_section_node(s, i) for i, s in enumerate(section_results)],
    }


def spec_sections_with_provenance(section_results: list[dict]) -> list[dict]:
    """Spec section entries carrying provenance (for promote-time links)."""
    return [
        {
            "section_id": s.get("section_id", ""),
            "title": s.get("title", ""),
            "provenance": s.get("provenance", []),
        }
        for s in section_results
    ]


def _first_chunk_ids(pack) -> tuple[str, str]:
    """(source_doc_id, chunk_id) of the first chunk in the pack, or ('', '')."""
    try:
        for source in pack.sources:
            for chunk in source.chunks:
                return chunk.source_doc_id, chunk.chunk_id
    except AttributeError:
        pass
    return "", ""


def _resolve_chunk(source_doc_id: str, pack) -> tuple[str, str]:
    """Return (chunk_id, source_doc_id) for the chunk matching the given source."""
    try:
        for source in pack.sources:
            for chunk in source.chunks:
                if chunk.source_doc_id == source_doc_id:
                    return chunk.chunk_id, chunk.source_doc_id
    except AttributeError:
        pass
    return "", ""


def _fallback_provenance(pack) -> list[dict]:
    result = []
    try:
        for source in pack.sources:
            for chunk in source.chunks[:3]:
                result.append({
                    "source": chunk.source_doc_id,
                    "source_doc_id": chunk.source_doc_id,
                    "confidence": 0.0,
                    "chunk_id": chunk.chunk_id,
                })
    except AttributeError:
        pass
    return result
