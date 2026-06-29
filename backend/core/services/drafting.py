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

# Plain prose, NOT JSON. Local models (llama3.1:8b) cannot reliably wrap a long
# multi-paragraph section inside a JSON string — they emit unescaped newlines /
# quotes and JSON parsing fails, leaving the section empty. Asking for raw text
# is robust: the whole response IS the section content. Provenance is resolved
# separately from the retrieved context pack, not from the model.
SECTION_PROMPT_TEMPLATE = """Scrivi il testo di una sezione di documento.

Titolo del documento: {title}
Titolo della sezione: {section_title}

Richiesta dell'utente (AUTORITATIVA — questi dati sono VERI, usali e scrivili
esplicitamente nel testo, NON come segnaposto):
{brief}

Sezioni già redatte (NON ripeterne il contenuto; questa sezione deve trattare
SOLO il proprio argomento «{section_title}»):
{previous_sections}

Ecco il contesto dai documenti sorgente:
{context_pack}

REGOLE (vincolanti):
- Scrivi SOLO il testo della sezione, in prosa professionale e chiara. NIENTE
  JSON, niente markdown, niente intestazioni o preamboli tipo "Ecco la sezione".
- Scrivi nella STESSA LINGUA della richiesta dell'utente qui sopra.
- I dati forniti dall'utente (nomi, parti, importi, durate, date, modalità) sono
  autoritativi: scrivili nel testo. Usa anche il contesto sorgente dove pertinente.
- Sintetizza e RIFORMULA con parole tue le informazioni del contesto: NON copiare
  frasi o periodi alla lettera dalle fonti.
- I documenti sorgente servono SOLO come riferimento di stile e struttura: NON
  copiarne nomi, parti, ragioni sociali, importi, date o luoghi. Per le parti, gli
  importi, le date e i luoghi usa ESCLUSIVAMENTE i dati della richiesta dell'utente.
- NON ripetere argomenti già trattati nelle sezioni precedenti elencate sopra.
- NON rifiutare e NON dichiarare di non poter svolgere il compito o di non poter
  consultare i file/documenti: redigi SEMPRE la sezione usando la richiesta
  dell'utente e la tua competenza giuridica generale, anche se il contesto
  sorgente è assente o scarso.
- NON inventare fatti che non sono né nella richiesta utente né nel contesto: per
  un dato realmente mancante usa un segnaposto esplicito tra parentesi quadre,
  es. [DA COMPLETARE: ...]. Il testo non deve mai essere vuoto."""

# Substrings that mark an LLM refusal/moralizing reply instead of section prose.
# Weak local models sometimes emit "Non posso accedere ai file…" on sparse
# context; such a reply must never reach the document.
_REFUSAL_MARKERS = (
    "non posso accedere",
    "non posso generare",
    "non sono in grado",
    "non riesco ad accedere",
    "non posso fornire",
    "siamo qui per discuterne",
    "as an ai",
    "i cannot",
    "i can't",
    "i'm unable",
    "i am unable",
)

# Appended to the prompt on a retry after a refusal, to force compliance.
_SECTION_RETRY_OVERRIDE = (
    "\n\nIMPORTANTE: scrivi ORA il testo della sezione. NON rispondere che non "
    "puoi farlo o che non hai accesso ai file/documenti: usa i dati della "
    "richiesta dell'utente e, per i dati mancanti, [DA COMPLETARE: ...]."
)


def _looks_like_refusal(text: str) -> bool:
    """True when the model declined/moralized instead of writing the section."""
    low = (text or "").lower()
    return any(m in low for m in _REFUSAL_MARKERS)


def _format_previous_sections(previous_sections: list[dict] | None) -> str:
    """Render already-written sections (title + short excerpt) for the prompt.

    The model uses this to avoid repeating earlier content; an empty list yields
    a sentinel so the prompt never carries a dangling placeholder.
    """
    if not previous_sections:
        return "(nessuna — questa è la prima sezione)"
    parts = []
    for s in previous_sections:
        if not isinstance(s, dict):
            continue
        title = str(s.get("title", "")).strip()
        excerpt = " ".join(str(s.get("content", "")).split())[:300]
        parts.append(f"- {title}: {excerpt}")
    return "\n".join(parts) or "(nessuna — questa è la prima sezione)"


def _pack_chunk_ids(pack) -> list[str]:
    """All chunk ids in a context pack (for cross-section dedup)."""
    ids: list[str] = []
    try:
        for source in pack.sources:
            for chunk in source.chunks:
                if chunk.chunk_id:
                    ids.append(chunk.chunk_id)
    except AttributeError:
        pass
    return ids


def _outline_from_slot_schema(doc_type: str) -> list[dict]:
    """Deterministic section outline from the slot schema of a known doc_type.

    Far more reliable than asking a weak local model to invent an outline (which
    produced generic English "Introduction/Main Content" sections unrelated to the
    requested document). Each slot becomes a section titled with the slot label
    and carrying the slot's retrieval hint for grounded per-section search.
    Returns [] for unknown / "other" types so the caller falls back to the LLM /
    default outline.
    """
    from core.doc_types import normalize as _normalize_doc_type
    from core.services.slot_schema import get_slot_schema_service

    canonical = _normalize_doc_type(doc_type)
    if canonical == "other":
        return []
    schema = get_slot_schema_service().get(canonical)
    if schema is None or not schema.slots:
        return []
    return [
        {
            "section_id": f"sec_{slot.id}",
            "title": slot.label,
            "query_hint": slot.retrieval_query_hint or slot.label,
        }
        for slot in schema.slots
    ]


def _normalize_sections(raw: object) -> list[dict]:
    """Coerce an LLM-produced 'sections' value into [{section_id, title}].

    Weak local models may emit sections as a list of strings, dicts without a
    section_id, or junk. Normalize so generate_section's `section.get(...)` never
    crashes the whole draft; drop entries without a title.
    """
    out: list[dict] = []
    for s in raw if isinstance(raw, list) else []:
        if isinstance(s, dict):
            title = str(s.get("title") or "").strip()
            sid = s.get("section_id") or f"sec_{uuid4().hex[:8]}"
        elif isinstance(s, str):
            title = s.strip()
            sid = f"sec_{uuid4().hex[:8]}"
        else:
            continue
        if title:
            out.append({"section_id": sid, "title": title})
    return out


class DraftService:
    def __init__(
        self,
        llm: LLMProvider | None = None,
        context_service: object | None = None,
    ):
        self._llm = llm
        self._context_service = context_service

    async def generate_spec(
        self,
        chat_session_id: str,
        messages: list[dict],
        llm: LLMProvider | None = None,
        doc_type: str = "",
    ) -> dict:
        last_message = messages[-1]["content"] if messages else ""
        # Aggregate ALL user messages as the brief: terms (parties, amount,
        # duration) are often stated across several turns, and using only the last
        # message leaves the section model without the real data — it then leans
        # on (and copies) whatever context it's given.
        user_msgs = [
            str(m.get("content", "")).strip()
            for m in messages
            if isinstance(m, dict) and m.get("role") == "user" and m.get("content")
        ]
        brief = "\n\n".join(user_msgs).strip() or last_message

        # Prefer a deterministic, type-correct outline from the slot schema; a weak
        # local model asked to invent the outline produced generic English
        # "Main Content" sections that had nothing to do with the requested doc.
        slot_sections = _outline_from_slot_schema(doc_type)
        if slot_sections:
            from core.doc_types import normalize as _normalize_doc_type

            return {
                "draft_id": f"draft_{uuid4().hex[:8]}",
                "chat_session_id": chat_session_id,
                # Empty -> the worker keeps the chat-provided title.
                "title": "",
                "sections": slot_sections,
                "brief": brief,
                "doc_type": _normalize_doc_type(doc_type),
                "metadata": {
                    "source": "slot_schema",
                    "message_count": len(messages),
                    "intent": last_message[:200] if last_message else "",
                },
            }

        provider = llm or self._llm
        if provider:
            prompt = SPEC_PROMPT_TEMPLATE.format(
                messages=last_message[:3000] if last_message else "(no messages)"
            )
            try:
                result = await provider.generate_structured(prompt, dict)
                sections = _normalize_sections(result.get("sections"))
                if sections:
                    return {
                        "draft_id": f"draft_{uuid4().hex[:8]}",
                        "chat_session_id": chat_session_id,
                        "title": result.get("title", f"Draft from chat {chat_session_id[:8]}"),
                        "sections": sections,
                        # Full user request — authoritative input for section content.
                        "brief": brief,
                        "metadata": {
                            "source": "chat",
                            "message_count": len(messages),
                            "intent": last_message[:200] if last_message else "",
                        },
                    }
                logger.warning("LLM spec returned no usable sections; using default outline")
            except Exception:
                logger.exception("LLM spec generation failed for session %s", chat_session_id)
        # Fallback when the LLM didn't return a usable outline (weak local models
        # often emit prose instead of JSON despite format=json). A sensible default
        # outline keeps the draft from being empty; section content is still driven
        # by the user's brief + corpus grounding.
        last_message = messages[-1]["content"] if messages else ""
        default_titles = [
            "Premesse e parti", "Oggetto",
            "Corrispettivo e durata", "Obblighi e risoluzione",
        ]
        spec = {
            "draft_id": f"draft_{uuid4().hex[:8]}",
            "chat_session_id": chat_session_id,
            "title": f"Draft from chat {chat_session_id[:8]}",
            "sections": [
                {"section_id": f"sec_{uuid4().hex[:8]}", "title": t} for t in default_titles
            ],
            "brief": brief,
            "metadata": {
                "source": "chat",
                "message_count": len(messages),
                "intent": last_message[:200] if last_message else "",
            },
        }
        return spec

    async def generate_section(  # noqa: PLR0913
        self,
        spec: dict,
        section: dict,
        context_pack: object | None = None,
        llm: LLMProvider | None = None,
        context_service: object | None = None,
        session_history: list[dict] | None = None,
        previous_sections: list[dict] | None = None,
        ground: bool = True,
    ) -> dict:
        provider = llm or self._llm
        ctx_svc = context_service or self._context_service
        section_id = section.get("section_id", f"sec_{uuid4().hex[:8]}")

        if context_pack is None:
            from core.services.context import ContextPack

            context_pack = ContextPack()

        # Brief-driven mode (ground=False): never touch the corpus. The corpus is
        # the user's OTHER documents; injecting them makes weak models copy their
        # parties/amounts/dates into the new document. With grounding off the
        # section is written purely from the brief.
        if ground and ctx_svc is not None and not self._has_context(context_pack):
            # Retrieve with the slot's query hint when present (e.g. "parti,
            # ragione sociale, sede legale") — far more targeted than the bare
            # section title, so each section pulls its own relevant chunks instead
            # of the same generic top-k. Pass session_history so chunks already
            # consumed by earlier sections are deduplicated.
            retrieval_query = section.get("query_hint") or section.get("title", "")
            context_pack = await ctx_svc.build_section_context(
                document_id=spec.get("document_id", ""),
                section_title=retrieval_query,
                section_id=section_id,
                session_history=session_history,
            )

        chunk_ids = _pack_chunk_ids(context_pack)

        if provider:
            # Ungrounded: never surface corpus text in the prompt, even if a pack
            # was passed — the brief is the only source of facts.
            context_text = self._format_context_pack(context_pack, ctx_svc) if ground else ""
            prompt = SECTION_PROMPT_TEMPLATE.format(
                title=spec.get("title", ""),
                section_title=section.get("title", ""),
                section_id=section_id,
                brief=spec.get("brief", "") or "(nessuna richiesta specifica)",
                previous_sections=_format_previous_sections(previous_sections),
                context_pack=context_text
                or (
                    "(Nessun documento sorgente disponibile: redigi la sezione "
                    "dalla richiesta dell'utente e dalla tua competenza generale.)"
                ),
            )
            try:
                # Plain text: the whole response is the section body. Provenance is
                # derived from the retrieved pack (not the model), and the content is
                # mapped to a single run — sourced if grounded, placeholder if not.
                response = await provider.generate(prompt)
                content = (response or "").strip()
                if not content or _looks_like_refusal(content):
                    # The model refused or returned nothing. Retry once with an
                    # explicit override; if it still refuses, emit a placeholder
                    # so a refusal sentence never lands in the document.
                    retry_resp = await provider.generate(prompt + _SECTION_RETRY_OVERRIDE)
                    retry = (retry_resp or "").strip()
                    if retry and not _looks_like_refusal(retry):
                        content = retry
                    else:
                        content = f"[DA COMPLETARE: {section.get('title', '')}]".strip()
                if ground:
                    provenance = self._build_provenance([], context_pack)
                    runs = self._build_runs({}, content, provenance)
                else:
                    # Brief-driven content is authored, not corpus-sourced: a plain
                    # run with no provenance and no placeholder mark.
                    provenance = []
                    runs = (
                        [{"text": content, "provenance": None, "placeholder": None}]
                        if content
                        else []
                    )
                return {
                    "section_id": section_id,
                    "title": section.get("title", ""),
                    "content": content,
                    "status": "draft",
                    "provenance": provenance,
                    "runs": runs,
                    "placeholders": [r["placeholder"] for r in runs if r["placeholder"]],
                    "context_chunk_ids": chunk_ids if ground else [],
                }
            except Exception:
                logger.exception(
                    "LLM section generation failed for %s/%s",
                    spec.get("draft_id", ""),
                    section_id,
                )
        # No content was produced (no provider, or the LLM call failed), so report
        # NO consumed chunks: those chunks weren't used and must stay available to
        # later sections instead of being withheld by the dedup.
        return {
            "section_id": section_id,
            "title": section.get("title", ""),
            "content": "",
            "status": "draft",
            "provenance": self._build_provenance([], context_pack),
            "runs": [],
            "placeholders": [],
            "context_chunk_ids": [],
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
