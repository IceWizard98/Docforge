import copy
import json
import logging
import uuid

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.llm.factory import get_llm_provider
from adapters.llm.utils import extract_action_from_reply
from adapters.minio.storage import MinioStorageAdapter
from adapters.postgresql.base import get_session
from adapters.postgresql.models import (
    ChatMessageModel,
    ChatSessionModel,
    CitationModel,
    DocumentModel,
    DraftModel,
    SourceDocumentModel,
)
from adapters.postgresql.pgvector import PgvectorAdapter
from api.middleware.auth import AuthUser, get_current_user
from api.schemas.chat import (
    ChatMessageRequest,
    ChatMessageResponse,
    ChatSessionCreate,
    ChatSessionDetailResponse,
    ChatSessionListResponse,
    ChatSessionResponse,
    SessionListItem,
    SessionUpdate,
)
from core.doc_types import normalize as normalize_doc_type
from core.services.context import ContextChunk, ContextPackService
from core.services.drafting import assemble_draft_content
from core.services.intent import IntentInferenceService
from core.services.search import RetrievalFilters
from core.services.slot_retrieval import SlotContextPack, SlotRetrievalService
from core.services.slot_schema import get_slot_schema_service
from workers.classification import classify_document_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# Loaded once: slot schemas are static data files.
_SLOT_SERVICE = get_slot_schema_service()

# Actions that indicate the user is drafting/editing a document (vs just chatting).
_DRAFTING_ACTIONS = {
    "draft", "create_section", "insert_clause", "rewrite_section", "propose_patches",
}


def _is_drafting_turn(action_data: dict | None) -> bool:
    return bool(action_data) and action_data.get("type") in _DRAFTING_ACTIONS



def _format_transparency(
    label: str, slot_pack: SlotContextPack, source_titles: list[str]
) -> tuple[str, list[dict]]:
    """Build the one-line "what I understood" summary + per-slot status list.

    Transparency surface: states the inferred type and which sources backed the
    reply, and exposes every slot's filled/missing/ambiguous state so the UI can
    flag what is still needed instead of letting the model invent it.
    """
    summary = f"Ho capito: {label}."
    names = [t for t in source_titles if t][:5]
    if names:
        summary += f" Fonti: {', '.join(names)}."
    else:
        summary += " Nessuna fonte rilevante trovata."
    slot_status = [
        {"slot_id": s.slot_id, "label": s.label, "status": s.status}
        for s in slot_pack.slots
    ]
    return summary, slot_status


async def _compute_transparency(
    db_session: AsyncSession, doc_model, text: str, sources: list[dict]
) -> tuple[str | None, list[dict]]:
    """Infer the target doc_type and run per-slot retrieval for transparency.

    Deterministic (no extra LLM call): the type comes from the open document or a
    keyword match; slot status comes from corpus retrieval. Best-effort — any
    failure yields no transparency rather than breaking the reply.
    """
    candidate = normalize_doc_type(getattr(doc_model, "doc_type", None)) if doc_model else "other"
    if candidate == "other":
        candidate = IntentInferenceService(llm=None, slot_service=_SLOT_SERVICE).detect_doc_type(text)
    schema = _SLOT_SERVICE.get(candidate) if candidate else None
    if schema is None:
        return None, []
    try:
        # No reranker here: bucketing doesn't need calibrated scores, and a
        # per-slot LLM rerank would add N LLM calls to the request path.
        slot_svc = SlotRetrievalService(
            pgvector=PgvectorAdapter(db_session),
            llm_provider=None,
            slot_service=_SLOT_SERVICE,
        )
        pack = await slot_svc.build_slot_context(candidate)
    except Exception:
        logger.exception("Transparency slot retrieval failed for %s", candidate)
        return None, []
    titles = [s.get("title", "") for s in sources]
    return _format_transparency(schema.label, pack, titles)


async def _retrieve_source_context(
    db_session: AsyncSession,
    query: str,
    filters: RetrievalFilters | None = None,
    collector: list[ContextChunk] | None = None,
) -> str:
    """Semantic retrieval over the uploaded source corpus.

    Returns a prompt-ready context string, or "" when nothing relevant is found
    or retrieval is unavailable. Wires the pgvector adapter + LLM reranker so the
    vector DB is actually queried during composition. When ``collector`` is given,
    the retrieved chunks are appended to it (for provenance/citation tracking).
    """
    if not query:
        return ""
    try:
        pgvector = PgvectorAdapter(db_session)
        context_svc = ContextPackService(pgvector=pgvector, llm_provider=get_llm_provider())
        pack = await context_svc.build_section_context(section_title=query, filters=filters)
        if pack and pack.sources:
            if collector is not None:
                for source in pack.sources:
                    collector.extend(source.chunks)
            return context_svc.build_prompt_context(pack)
    except Exception:
        logger.exception("Failed to retrieve source context")
    return ""


async def _build_message_sources(
    db_session: AsyncSession, chunks: list[ContextChunk]
) -> list[dict]:
    """Turn collected retrieval chunks into SourceRef dicts for the chat message.

    Dedups by chunk_id, resolves source filenames in a single batch query, and
    falls back to the source id as title when the file row is missing.
    """
    if not chunks:
        return []
    seen: set[str] = set()
    unique: list[ContextChunk] = []
    for c in chunks:
        if c.chunk_id in seen:
            continue
        seen.add(c.chunk_id)
        unique.append(c)

    source_ids: set[uuid.UUID] = set()
    for c in unique:
        try:
            source_ids.add(uuid.UUID(str(c.source_doc_id)))
        except (ValueError, AttributeError, TypeError):
            continue

    titles: dict[str, str] = {}
    if source_ids:
        result = await db_session.execute(
            select(SourceDocumentModel).where(SourceDocumentModel.id.in_(source_ids))
        )
        for src in result.scalars().all():
            titles[str(src.id)] = src.filename

    refs: list[dict] = []
    for c in unique:
        sid = str(c.source_doc_id)
        refs.append({
            "sourceDocId": sid,
            "title": titles.get(sid, sid),
            "snippet": (c.content or "")[:160],
            "chunkId": c.chunk_id,
            "confidence": round(float(c.relevance_score), 4),
        })
    return refs


async def _write_citations(
    db_session: AsyncSession, message_id: uuid.UUID, chunks: list[ContextChunk]
) -> None:
    """Persist one CitationModel per unique retrieved chunk backing a message.

    Each insert runs in a savepoint so a stale chunk_id (FK violation) is skipped
    without poisoning the surrounding transaction.
    """
    if not chunks:
        return
    seen: set[str] = set()
    for c in chunks:
        if c.chunk_id in seen:
            continue
        seen.add(c.chunk_id)
        try:
            source_uuid = uuid.UUID(str(c.source_doc_id))
        except (ValueError, AttributeError, TypeError):
            source_uuid = None
        try:
            async with db_session.begin_nested():
                db_session.add(CitationModel(
                    id=uuid.uuid4(),
                    chat_message_id=message_id,
                    chunk_id=c.chunk_id,
                    source_doc_id=source_uuid,
                    confidence=round(float(c.relevance_score), 4),
                ))
        except SQLAlchemyError:
            logger.warning("Skipped citation for chunk %s (FK/constraint)", c.chunk_id)


async def _ingest_chat_attachment(
    db_session: AsyncSession,
    filename: str,
    data: bytes,
    content_type: str | None,
    document_id,
) -> str:
    """Register a chat attachment as an indexed SourceDocument. Returns parsed text.

    Best-effort: on any failure returns "" and the caller falls back to raw decode.
    """
    from pathlib import Path

    from api.routes.documents import _parse_to_prosemirror, _prosemirror_to_text

    ext = Path(filename).suffix.lower()
    if ext not in {".pdf", ".docx", ".txt", ".md"}:
        return ""
    try:
        prosemirror = _parse_to_prosemirror(data, ext)
        parsed_text = _prosemirror_to_text(prosemirror)
        source_id = uuid.uuid4()
        storage = MinioStorageAdapter()
        stored_path = await storage.upload(
            path=f"source/{source_id}/{filename}",
            data=data,
            content_type=content_type or "application/octet-stream",
        )
        source = SourceDocumentModel(
            id=source_id,
            document_id=document_id,
            filename=filename,
            # Extension is not a doc type; normalize ("other" until classified).
            doc_type=normalize_doc_type(ext.lstrip(".")),
            file_key=stored_path,
            status="uploaded",
            parsed_content=prosemirror,
            parsed_text=parsed_text,
        )
        # Savepoint so a failed insert doesn't poison the outer transaction
        # (which still must persist the user + assistant messages).
        async with db_session.begin_nested():
            db_session.add(source)
        classify_document_task.apply_async((str(source_id), None), countdown=3)
        return parsed_text
    except Exception:
        logger.exception("Failed to ingest chat attachment %s", filename)
        return ""


def _section_title(section: dict) -> str:
    """Best-effort section title: attrs.title, else first heading text."""
    attrs = section.get("attrs", {}) if isinstance(section, dict) else {}
    if attrs.get("title"):
        return str(attrs["title"])
    for node in section.get("content", []) or []:
        if isinstance(node, dict) and node.get("type") == "heading":
            for inline in node.get("content", []) or []:
                if isinstance(inline, dict) and inline.get("type") == "text":
                    return inline.get("text", "")
    return "(senza titolo)"


def _document_outline(content: dict | None) -> str:
    """Clean section map (sectionId + title + status) the LLM can target reliably."""
    if not isinstance(content, dict):
        return ""
    lines = []
    for node in content.get("content", []) or []:
        if isinstance(node, dict) and node.get("type") == "section":
            attrs = node.get("attrs", {})
            sid = attrs.get("sectionId", "")
            status_str = attrs.get("status", "draft")
            lines.append(f'- [{sid}] "{_section_title(node)}" (stato: {status_str})')
    if not lines:
        return ""
    header = "Struttura del documento corrente (usa questi sectionId esatti per modificare):\n"
    return header + "\n".join(lines)


async def _corpus_catalog(db_session: AsyncSession, limit: int = 30) -> str:
    """Catalog of the uploaded sources so the agent can answer about them."""
    try:
        result = await db_session.execute(
            select(SourceDocumentModel)
            .order_by(SourceDocumentModel.created_at.desc())
            .limit(limit)
        )
        sources = result.scalars().all()
    except SQLAlchemyError:
        logger.exception("Failed to load corpus catalog")
        return ""
    if not sources:
        return ""
    lines = []
    for s in sources:
        tags = ", ".join(s.tags or []) if isinstance(s.tags, list) else ""
        created = s.created_at.date().isoformat() if s.created_at else ""
        meta = " · ".join(p for p in [s.doc_type, s.language, created] if p)
        tag_str = f" [tag: {tags}]" if tags else ""
        lines.append(f"- {s.filename} ({meta}){tag_str}")
    return "Documenti caricati dall'utente (catalogo):\n" + "\n".join(lines)


def _make_corpus_executor(db_session, filters=None, collector=None):
    """Build the tool executor used by the agent (search_corpus / list_documents).

    ``filters`` scopes corpus search (e.g. by doc_type); ``collector`` accumulates
    the chunks the agent actually retrieved so the caller can build sources/citations.
    """
    async def _corpus_executor(name: str, args: dict) -> str:
        if name == "search_corpus":
            found = await _retrieve_source_context(
                db_session, args.get("query", ""), filters=filters, collector=collector
            )
            return found or "Nessun passaggio rilevante trovato."
        if name == "list_documents":
            cat = await _corpus_catalog(db_session)
            return cat or "Nessun documento caricato."
        return f"Strumento sconosciuto: {name}"
    return _corpus_executor


async def _build_chat_context(db_session, chat_model, current_user) -> tuple[str, object]:
    """Seed prompt context with the open document's preview + section outline.

    Corpus knowledge is fetched on demand by the agent's tools, not stuffed here.
    Returns (document_context, doc_model | None).
    """
    document_context = ""
    doc_model = None
    if chat_model.document_id:
        doc_result = await db_session.execute(
            select(DocumentModel).where(DocumentModel.id == chat_model.document_id)
        )
        doc_model = doc_result.scalar_one_or_none()
        if doc_model:
            preview = json.dumps(doc_model.content)[:3000] if doc_model.content else ""
            document_context = (
                f"Document context:\nTitle: {doc_model.title}\n"
                f"Type: {doc_model.doc_type}\nContent (first 3000 chars):\n{preview}"
            )
            outline = _document_outline(doc_model.content)
            if outline:
                document_context += "\n\n=== Struttura documento ===\n" + outline
    return document_context, doc_model


async def _generate_chat_reply(provider, system_prompt: str, user_text: str, executor) -> dict:
    """Run the agent (native/emulated) and parse the final JSON {reply, action, sources}.

    Centralises LLM error handling so all chat entry points behave identically.
    """
    from adapters.llm.utils import extract_json
    from core.services.agent import agentic_answer

    def _err(reply: str) -> dict:
        return {"reply": reply, "action": None, "sources": []}

    try:
        final_text = await agentic_answer(provider, system_prompt, user_text, executor)
        try:
            return extract_json(final_text)
        except Exception:
            return _err(final_text)
    except ValueError as e:
        msg = str(e)
        if "API key" in msg or "not configured" in msg:
            logger.error("LLM configuration error: %s", msg)
            return _err(
                "L'assistente AI non è ancora configurato. "
                "L'amministratore deve impostare le chiavi API nel file .env."
            )
        logger.exception("LLM generation ValueError: %s", msg)
        return _err("Si è verificato un errore durante la generazione. Per favore, riprova.")
    except (httpx.ConnectError, httpx.NetworkError, httpx.TimeoutException) as e:
        logger.exception("LLM service unreachable: %s", e)
        return _err(
            "Il servizio AI non è al momento raggiungibile. "
            "Verifica che il provider LLM sia in esecuzione e riprova."
        )
    except Exception:
        logger.exception("LLM generation failed")
        return _err("Si è verificato un errore imprevisto. Per favore, riprova più tardi.")


async def _propose_patch_set(
    db_session, current_user, doc_model, operations: list[dict], summary: str
) -> dict:
    """Persist a reviewable PatchSetModel (status 'proposed') and return a chat action.

    Surgical edits go through PatchService/patching (target_path-aware, structure
    preserving) and are applied only after the user accepts them — no flattening.
    """
    from adapters.postgresql.models import PatchSetModel
    from api.routes.patches import _enrich_operations

    ps_id = uuid.uuid4()
    patch_set = PatchSetModel(
        id=ps_id,
        document_id=doc_model.id,
        version_from=doc_model.version,
        version_to=doc_model.version + 1,
        status="proposed",
        summary=(summary or "Modifiche proposte")[:500],
        operations=_enrich_operations(operations, str(ps_id)),
        created_by=uuid.UUID(current_user.user_id),
    )
    db_session.add(patch_set)
    await db_session.flush()
    return {
        "action": "patches_proposed",
        "label": "Modifiche proposte — rivedi e applica",
        "payload": {
            "patch_set_id": str(ps_id),
            "document_id": str(doc_model.id),
            "summary": patch_set.summary,
            "operations": patch_set.operations,
        },
    }


def _resolve_assistant_action(result_data: dict) -> tuple[str, dict | None, list]:
    """Resolve the visible reply, the structured action, and the initial actions list.

    Falls back to extracting an action embedded in the reply text (and stripping
    that JSON out of the visible message). Pure — no DB access.
    """
    ai_content = result_data.get("reply", "")
    action_data = result_data.get("action")

    if not action_data:
        extracted = extract_action_from_reply(ai_content)
        if extracted:
            action_data = extracted
            try:
                start = ai_content.find("{")
                end = ai_content.rfind("}")
                if start != -1 and end != -1:
                    candidate = ai_content[start:end + 1]
                    json.loads(candidate)  # verify it's valid JSON
                    cleaned = (ai_content[:start] + ai_content[end + 1:]).strip()
                    ai_content = cleaned or "Ho elaborato la richiesta."
            except (json.JSONDecodeError, Exception):
                pass

    actions: list = []
    if action_data and isinstance(action_data, dict):
        actions = [{
            "action": action_data.get("type"),
            "label": action_data.get("label", ""),
            "payload": action_data.get("params", {}),
        }]
    return ai_content, action_data, actions


async def _handle_document_action(  # noqa: PLR0913
    action_data: dict | None,
    doc_model,
    db_session,
    current_user,
    provider,
    fallback_instructions: str,
) -> tuple[list | None, dict | None]:
    """Apply a document-mutation action to the open document.

    Returns (actions_override, doc_content_updated). actions_override is None when
    the action produced no result (caller keeps its existing actions); otherwise it
    replaces them. doc_content_updated is the new content to push to the editor, or
    None when nothing was written (e.g. surgical patch proposals, which are applied
    only after review).
    """
    if not action_data or doc_model is None:
        return None, None

    action_type = action_data.get("type", "")
    params = action_data.get("params", {})

    if action_type == "create_section":
        title = params.get("title", "Nuova sezione")
        content_text = params.get("content", "")
        section_id = f"sec_{uuid.uuid4().hex[:8]}"
        current_doc = copy.deepcopy(doc_model.content) if doc_model.content else {"type": "doc", "content": []}
        sections = current_doc.get("content", [])
        section_number = len(sections) + 1
        sections.append({
            "type": "section",
            "attrs": {"sectionId": section_id, "title": title, "number": section_number, "status": "draft"},
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": content_text}]}],
        })
        doc_model.content = current_doc
        try:
            await db_session.flush()
        except SQLAlchemyError:
            logger.exception("Failed to create section in document")
            return None, None
        return [{
            "action": "section_created",
            "label": f"Sezione aggiunta: {title}",
            "payload": {"section_id": section_id, "title": title, "document_content": current_doc},
        }], current_doc

    if action_type == "insert_clause":
        section_id = params.get("section_id", "")
        clause_text = params.get("clause_text", "")
        if not (section_id and clause_text):
            return None, None
        current_doc = copy.deepcopy(doc_model.content) if doc_model.content else {"type": "doc", "content": []}
        for section in current_doc.get("content", []):
            attrs = section.get("attrs", {}) if isinstance(section, dict) else {}
            if attrs.get("sectionId") == section_id:
                section.setdefault("content", []).append({
                    "type": "clause",
                    "attrs": {"clauseId": f"cl_{uuid.uuid4().hex[:8]}"},
                    "content": [{"type": "paragraph", "content": [{"type": "text", "text": clause_text}]}],
                })
                break
        doc_model.content = current_doc
        try:
            await db_session.flush()
        except SQLAlchemyError:
            logger.exception("Failed to insert clause")
            return None, None
        return [{
            "action": "clause_inserted",
            "label": "Clausola inserita",
            "payload": {"section_id": section_id, "document_content": current_doc},
        }], current_doc

    if action_type == "rewrite_section":
        # Surgical: propose a reviewable replace patch instead of flattening.
        section_id = params.get("section_id", "")
        new_content = params.get("content", "")
        if not (section_id and new_content):
            return None, None
        ops = [{
            "operation": "replace",
            "target_section": section_id,
            "content": {"content": [
                {"type": "paragraph", "content": [{"type": "text", "text": new_content}]}
            ]},
            "rationale": "Riscrittura sezione richiesta dall'utente",
        }]
        try:
            action = await _propose_patch_set(
                db_session, current_user, doc_model, ops, "Riscrittura sezione"
            )
        except SQLAlchemyError:
            logger.exception("Failed to propose rewrite patch")
            return None, None
        return [action], None

    if action_type in ("propose_patches", "suggest_edit"):
        instructions = params.get("instructions") or fallback_instructions
        try:
            from core.services.patching import PatchService
            doc_dict = {
                "id": str(doc_model.id),
                "title": doc_model.title,
                "version": doc_model.version,
                "content": doc_model.content or {},
            }
            plan = await PatchService(llm=provider).generate_patch_plan(
                doc_dict, instructions, provider
            )
            ops = plan.get("operations", [])
            if ops:
                action = await _propose_patch_set(
                    db_session, current_user, doc_model, ops,
                    plan.get("summary", "Modifiche proposte"),
                )
                return [action], None
        except SQLAlchemyError:
            logger.exception("Failed to propose patches")
        except Exception:
            logger.exception("Patch plan generation failed")
        return None, None

    return None, None


@router.post("/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    body: ChatSessionCreate,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    chat_id = uuid.uuid4()

    if body.document_id:
        doc_result = await session.execute(
            select(DocumentModel).where(
                DocumentModel.id == body.document_id,
                DocumentModel.created_by == uuid.UUID(current_user.user_id),
            )
        )
        if doc_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )

    model = ChatSessionModel(
        id=chat_id,
        document_id=body.document_id,
        user_id=current_user.user_id,
        title=body.title,
        context_type=body.context_type,
    )
    session.add(model)
    try:
        await session.flush()
        system_msg = ChatMessageModel(
            id=uuid.uuid4(),
            session_id=chat_id,
            role="system",
            content=(
                "Sei un assistente specializzato nella creazione e revisione di "
                "documenti professionali. "
                "Il tuo nome è DocForge AI. "
                "Puoi aiutare l'utente a:"
                "\n- Scrivere e modificare documenti"
                "\n- Suggerire miglioramenti e modifiche"
                "\n- Generare bozze da descrizioni"
                "\n- Validare contenuti e struttura"
                "\n- Rispondere a domande sul documento"
                "\n- Proporre azioni specifiche quando pertinente"
                "\n"
                "\nRegole:"
                "\n- Rispondi sempre in italiano"
                "\n- Sii conciso e professionale"
                "\n- Quando proponi azioni, spiega brevemente cosa farai"
                "\n- Non inventare fatti o citazioni non presenti nel documento"
                "\n- Se non hai abbastanza contesto, chiedi chiarimenti"
            ),
        )
        session.add(system_msg)
        await session.flush()
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Database constraint violation",
        )
    return ChatSessionResponse.model_validate(model)


@router.get("/sessions", response_model=ChatSessionListResponse)
async def list_sessions(
    document_id: uuid.UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    current_user: AuthUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_session),
):
    base = select(ChatSessionModel).where(
        ChatSessionModel.status != "archived",
        ChatSessionModel.user_id == uuid.UUID(current_user.user_id),
    )

    if document_id:
        base = base.where(ChatSessionModel.document_id == document_id)

    total = await db_session.scalar(select(func.count()).select_from(base.subquery())) or 0
    offset = (page - 1) * per_page
    result = await db_session.execute(
        base.order_by(ChatSessionModel.updated_at.desc()).offset(offset).limit(per_page)
    )
    models = list(result.scalars().all())

    session_ids = [m.id for m in models]
    last_messages: dict[uuid.UUID, str] = {}

    if session_ids:
        latest_subq = (
            select(
                ChatMessageModel.session_id,
                func.max(ChatMessageModel.created_at).label("max_created_at"),
            )
            .where(ChatMessageModel.session_id.in_(session_ids))
            .group_by(ChatMessageModel.session_id)
            .subquery()
        )
        msg_query = (
            select(ChatMessageModel)
            .join(
                latest_subq,
                and_(
                    ChatMessageModel.session_id == latest_subq.c.session_id,
                    ChatMessageModel.created_at == latest_subq.c.max_created_at,
                ),
            )
        )
        msg_result = await db_session.execute(msg_query)
        for msg in msg_result.scalars().all():
            last_messages[msg.session_id] = msg.content[:100]

    data = []
    for m in models:
        preview = last_messages.get(m.id)
        data.append(
            SessionListItem(
                id=m.id,
                document_id=m.document_id,
                user_id=m.user_id,
                title=m.title,
                context_type=m.context_type,
                status=m.status,
                created_at=m.created_at,
                updated_at=m.updated_at,
                last_message_preview=preview,
            )
        )

    return ChatSessionListResponse(
        data=data,
        meta={"page": page, "per_page": per_page, "total": total},
    )


@router.get("/sessions/{session_id}", response_model=ChatSessionDetailResponse)
async def get_chat_session(
    session_id: uuid.UUID,
    current_user: AuthUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_session),
):
    result = await db_session.execute(
        select(ChatSessionModel).where(
            ChatSessionModel.id == session_id,
            ChatSessionModel.user_id == uuid.UUID(current_user.user_id),
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    msgs_result = await db_session.execute(
        select(ChatMessageModel)
        .where(ChatMessageModel.session_id == model.id)
        .order_by(ChatMessageModel.created_at)
    )
    messages = [
        ChatMessageResponse.model_validate(m) for m in msgs_result.scalars().all()
    ]
    detail = ChatSessionDetailResponse.model_validate(model)
    detail.messages = messages
    return detail


async def _execute_draft_action(
    action_data: dict | None,
    session_id: uuid.UUID,
    doc_model: DocumentModel | None,
    current_user: AuthUser,
    db_session: AsyncSession,
) -> tuple[uuid.UUID | None, dict | None, list[dict]]:
    """Execute a draft action: create DraftModel and return (draft_id, doc_content, actions).

    Returns (None, None, []) if no draft action should be executed or on failure.
    """
    if not action_data or action_data.get("type") != "draft":
        return None, None, []

    try:
        params = action_data.get("params", {})
        sections = params.get("sections", [])
        if not sections:
            return None, None, []

        draft_id = uuid.uuid4()
        # Single source of truth for section-node assembly, shared with the async
        # draft worker (build_section_node applies per-span provenance/placeholder
        # marks and the status attr consistently).
        doc_content = assemble_draft_content(sections)

        draft_model = DraftModel(
            id=draft_id,
            chat_session_id=session_id,
            document_id=doc_model.id if doc_model else None,
            title=params.get("title", "Documento"),
            spec={
                "title": params.get("title", ""),
                "doc_type": params.get("doc_type", ""),
                "language": params.get("language", "it"),
                "sections": sections,
            },
            content=copy.deepcopy(doc_content),
            status="completed",
            progress={"total_sections": len(sections), "completed_sections": len(sections)},
        )
        db_session.add(draft_model)
        try:
            await db_session.flush()
        except SQLAlchemyError:
            logger.exception("Failed to persist auto-draft")
            return None, None, []

        actions = [{
            "action": "draft_ready",
            "label": f"Bozza generata: {params.get('title', 'Documento')}",
            "payload": {
                "draft_id": str(draft_id),
                "title": params.get("title", ""),
                "doc_type": params.get("doc_type", ""),
                "section_count": len(sections),
                "document_content": doc_content,
            },
        }]
        return draft_id, doc_content, actions
    except Exception:
        logger.exception("Auto-draft creation failed")
        return None, None, []


@router.post("/sessions/{session_id}/messages", response_model=ChatMessageResponse)
async def send_message(
    session_id: uuid.UUID,
    body: ChatMessageRequest,
    current_user: AuthUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_session),
):
    result = await db_session.execute(
        select(ChatSessionModel).where(
            ChatSessionModel.id == session_id,
            ChatSessionModel.user_id == uuid.UUID(current_user.user_id),
        )
    )
    chat_model = result.scalar_one_or_none()
    if chat_model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    user_msg = ChatMessageModel(
        id=uuid.uuid4(),
        session_id=session_id,
        role="user",
        content=body.content,
    )
    db_session.add(user_msg)
    try:
        await db_session.flush()
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Database constraint violation",
        )

    # The agent pulls corpus data on demand via tools (search_corpus /
    # list_documents) — native for tool-capable providers, emulated otherwise —
    # so we only seed the prompt with the open document's preview + outline.
    document_context, doc_model = await _build_chat_context(
        db_session, chat_model, current_user
    )

    msg_result = await db_session.execute(
        select(ChatMessageModel)
        .where(
            ChatMessageModel.session_id == session_id,
            ChatMessageModel.role != "system",
        )
        .order_by(ChatMessageModel.created_at.desc())
        .limit(6)
    )
    recent_messages = list(reversed(msg_result.scalars().all()))
    history_lines = [
        f"{'Utente' if m.role == 'user' else 'Assistente'}: {m.content[:500]}"
        for m in recent_messages
    ]
    history = "\n".join(history_lines)

    system_prompt_parts = [
        "Sei un REDATTORE DI DOCUMENTI professionale. Devi CREARE documenti completi, non solo parlarne.",
        "",
        "=== REGOLE FONDAMENTALI ===",
        "1. Se l'utente chiede di scrivere/creare/generare un documento, produci SUBITO il documento.",
        "2. Usa action type 'draft' per generare. Includi title, doc_type, e sections con contenuti COMPLETI.",
        "3. Scrivi contenuti PROFESSIONALI e DETTAGLIATI, MA ogni affermazione deve"
        " essere riconducibile alle fonti caricate. NON inventare fatti, clausole,"
        " nomi, importi o date non presenti nelle fonti: se un'informazione manca,"
        " inserisci un segnaposto esplicito tra parentesi quadre (es. \"[DA"
        " DEFINIRE: foro competente]\") invece di inventarla. Per i contratti una"
        " clausola allucinata è un danno.",
        "4. Fai domande solo se mancano informazioni critiche (es. tipo documento, parti).",
        "5. Per MODIFICARE il documento aperto usa SOLO i sectionId esatti elencati in"
        " '=== Struttura documento ==='. Le modifiche a contenuto esistente sono"
        " proposte come DIFF da rivedere (l'utente accetta/rifiuta): usa"
        " 'rewrite_section' (riscrive una sezione) o 'propose_patches' (modifiche"
        " mirate, params: {\"instructions\":\"cosa cambiare\"}). Per aggiungere usa"
        " 'create_section' o 'insert_clause'.",
        "6. Per informazioni sui documenti caricati (quali, tipo, riassunti, confronti)"
        " usa gli strumenti 'search_corpus' e 'list_documents' se disponibili,"
        " altrimenti le sezioni '=== Catalogo documenti ===' / '=== Documenti di"
        " riferimento ==='. Rispondi con 'answer_question' e cita i nomi file.",
        "7. Dopo aver usato gli strumenti, restituisci SEMPRE la risposta finale nel"
        " formato JSON richiesto sotto.",
        "",
        document_context,
        "",
        "Chat history:",
        history,
        "",
        "=== AZIONI DISPONIBILI ===",
        '- "draft": Genera bozza completa. params: {"title":"...","doc_type":"...",'
        '"language":"it","sections":[{"title":"...","content":"...",'
        '"provenance":[{"source_doc_id":"<id da search_corpus>","chunk_id":"...",'
        '"confidence":0.0}],'
        '"runs":[{"text":"...","provenance":{"source_doc_id":"...","chunk_id":"...",'
        '"confidence":0.0}|null,"placeholder":{"slot_id":"...","reason":"..."}|null}]}]}.'
        ' Per ogni sezione: usa "runs" per marcare ogni frammento come sorgentato'
        ' (provenance) o segnaposto (placeholder), e "provenance" per le fonti'
        ' della sezione. Marca segnaposto ciò che non è nelle fonti.',
        '- "create_section": Aggiungi sezione al documento. params: {"title":"...","content":"..."}',
        '- "insert_clause": Inserisci clausola. params: {"section_id":"...","clause_text":"..."}',
        '- "rewrite_section": Riscrivi una sezione (diff da rivedere). params: {"section_id":"...","content":"..."}',
        '- "propose_patches": Modifiche mirate al documento (diff da rivedere). params: {"instructions":"..."}',
        '- "answer_question": Solo risposta informativa.',
        "",
        "=== FORMATO RISPOSTA (JSON) ===",
        "Rispondi SEMPRE in italiano. Restituisci SOLO JSON valido:",
        "{",
        '  "reply": "messaggio diretto in italiano (SOLO testo, niente JSON qui)",',
        '  "action": null | {"type":"draft","label":"Genera","params":{...}},',
        '  "sources": []',
        "}",
        "IMPORTANTE: 'reply' deve contenere SOLO il testo per l'utente. NON inserire JSON in 'reply'. L'azione va nel campo 'action'.",
        "Se sono disponibili documenti di riferimento, usali come base per la scrittura. Cita le fonti quando possibile.",
    ]
    system_prompt = "\n".join(system_prompt_parts)

    edit_hint = ""
    if body.edit_context:
        if body.edit_context.selected_text:
            edit_hint += f'\nL\'utente ha selezionato questo testo nel documento: "{body.edit_context.selected_text}"'
        if body.edit_context.section_id:
            edit_hint += f"\nL'utente sta lavorando sulla sezione: {body.edit_context.section_id}"
    provider = get_llm_provider()
    # Search the WHOLE corpus: reference sources for a document need not share its
    # type (e.g. a contract draws on company profiles, NDAs, prior contracts), and
    # legacy rows may carry un-normalized doc_type values. No doc_type scoping.
    retrieved_chunks: list[ContextChunk] = []
    executor = _make_corpus_executor(db_session, filters=None, collector=retrieved_chunks)
    user_text = f"{edit_hint}\n\nMessaggio utente: {body.content}".strip()
    result_data = await _generate_chat_reply(provider, system_prompt, user_text, executor)

    ai_content, action_data, actions = _resolve_assistant_action(result_data)

    # Auto-execute draft action: create DraftModel with LLM-generated sections
    draft_id = None
    doc_content = None  # Fix 5: initialize outside for later use
    if action_data and action_data.get("type") == "draft":
        draft_id, doc_content, draft_actions = await _execute_draft_action(
            action_data, session_id, doc_model, current_user, db_session
        )
        if draft_actions:
            actions = draft_actions

    if not actions:
        assistant_count = await db_session.scalar(
            select(func.count()).where(
                ChatMessageModel.session_id == session_id,
                ChatMessageModel.role == "assistant",
            )
        ) or 0
        if assistant_count == 0:
            actions = [
                {
                    "action": "suggest_draft",
                    "label": "Genera bozza",
                    "payload": {"session_id": str(session_id)},
                },
                {
                    "action": "suggest_patches",
                    "label": "Proponi modifiche",
                    "payload": {"session_id": str(session_id)},
                },
            ]

    # Prefer real provenance from what the agent actually retrieved; fall back to
    # whatever the model declared (typically empty).
    sources = await _build_message_sources(db_session, retrieved_chunks)
    if not sources:
        sources = result_data.get("sources", [])

    # Execute document-modification actions (create/insert/rewrite/propose) on the
    # open document. Override actions only when the handler produced a result.
    override_actions, doc_content_updated = await _handle_document_action(
        action_data, doc_model, db_session, current_user, provider, body.content
    )
    if override_actions is not None:
        actions = override_actions

    # When draft was created and a document is open, apply draft content to the document
    if draft_id and doc_model is not None and doc_content is not None and not doc_content_updated:
        try:
            doc_model.content = doc_content
            await db_session.flush()
            doc_content_updated = doc_content
        except Exception:
            logger.exception("Failed to apply draft content to document")

    # Transparency only on drafting turns (or when sources were used): a plain
    # conversational reply shouldn't pay a full per-slot corpus scan.
    intent_summary, slot_status = None, []
    if _is_drafting_turn(action_data) or retrieved_chunks:
        intent_summary, slot_status = await _compute_transparency(
            db_session, doc_model, body.content, sources
        )

    # Surgical edits are proposed as reviewable PatchSets via the 'propose_patches'
    # / 'rewrite_section' actions above (granular accept/reject), not inline here.
    ai_msg = ChatMessageModel(
        id=uuid.uuid4(),
        session_id=session_id,
        role="assistant",
        content=ai_content,
        actions=actions,
        patches=[],
        sources=sources or [],
        intent_summary=intent_summary,
        slot_status=slot_status,
    )
    db_session.add(ai_msg)
    try:
        await db_session.flush()
    except SQLAlchemyError:
        logger.exception("Failed to persist assistant message for session %s", session_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to persist assistant message",
        )

    # Persist provenance: one citation per retrieved chunk backing this reply.
    await _write_citations(db_session, ai_msg.id, retrieved_chunks)

    return ChatMessageResponse.model_validate(ai_msg)


@router.get("/sessions/{session_id}/stream")
async def stream_chat(
    session_id: uuid.UUID,
    current_user: AuthUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_session),
):
    """SSE endpoint that streams LLM token by token for the last assistant message."""
    result = await db_session.execute(
        select(ChatSessionModel).where(
            ChatSessionModel.id == session_id,
            ChatSessionModel.user_id == uuid.UUID(current_user.user_id),
        )
    )
    chat_model = result.scalar_one_or_none()
    if chat_model is None:
        raise HTTPException(status_code=404, detail="Session not found")

    msg_result = await db_session.execute(
        select(ChatMessageModel)
        .where(
            ChatMessageModel.session_id == session_id,
            ChatMessageModel.role == "user",
        )
        .order_by(ChatMessageModel.created_at.desc())
        .limit(1)
    )
    last_user_msg = msg_result.scalar_one_or_none()
    if last_user_msg is None:
        raise HTTPException(status_code=400, detail="No user message to respond to")

    # Streaming can't run a tool loop, so do a single retrieval
    # for the user's message and seed it alongside the document context.
    document_context, doc_model = await _build_chat_context(
        db_session, chat_model, current_user
    )
    source_context = await _retrieve_source_context(
        db_session, last_user_msg.content
    )
    if source_context:
        document_context += "\n\n=== Documenti di riferimento ===\n" + source_context

    history_result = await db_session.execute(
        select(ChatMessageModel)
        .where(
            ChatMessageModel.session_id == session_id,
            ChatMessageModel.role != "system",
        )
        .order_by(ChatMessageModel.created_at.desc())
        .limit(6)
    )
    recent_messages = list(reversed(history_result.scalars().all()))
    history_lines = [
        f"{'Utente' if m.role == 'user' else 'Assistente'}: {m.content[:500]}"
        for m in recent_messages
    ]
    history = "\n".join(history_lines)

    system_prompt = f"""Sei un assistente per la stesura e revisione di documenti professionali.

{document_context}

Chat history (ultimi messaggi):
{history}

Il tuo compito è aiutare l'utente con la creazione, modifica e validazione di documenti.
Rispondi sempre in italiano in modo naturale e colloquiale, come un collega esperto.
Non usare formattazione JSON nella risposta - parla direttamente all'utente."""

    prompt = f"{system_prompt}\n\nMessaggio utente: {last_user_msg.content}"

    async def event_generator():
        full_response: list[str] = []
        try:
            provider = get_llm_provider()

            if hasattr(provider, 'generate_stream'):
                async for chunk in provider.generate_stream(prompt):
                    if chunk:
                        full_response.append(chunk)
                        yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
            else:
                response = await provider.generate(prompt)
                full_response.append(response)
                yield f"data: {json.dumps({'type': 'chunk', 'content': response})}\n\n"

            # Persist assistant message after streaming completes
            ai_text = "".join(full_response)
            if ai_text:
                ai_msg = ChatMessageModel(
                    id=uuid.uuid4(),
                    session_id=session_id,
                    role="assistant",
                    content=ai_text,
                )
                db_session.add(ai_msg)
                try:
                    await db_session.flush()
                except SQLAlchemyError:
                    logger.exception("Failed to persist streamed assistant message for session %s", session_id)

            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except (httpx.ConnectError, httpx.NetworkError, httpx.TimeoutException):
            logger.exception("Stream: LLM service unreachable")
            err_data = json.dumps({
                'type': 'error',
                'content': 'Il servizio AI non è al momento raggiungibile. Verifica che il provider LLM sia in esecuzione.'
            })
            yield f"data: {err_data}\n\n"
        except ValueError as e:
            logger.exception("Stream: ValueError: %s", e)
            err_data = json.dumps({
                'type': 'error',
                'content': 'Errore di configurazione del servizio AI. Verificare le chiavi API nel file .env.'
            })
            yield f"data: {err_data}\n\n"
        except Exception:
            logger.exception("Stream generation failed")
            err_data = json.dumps({
                'type': 'error',
                'content': 'Errore imprevisto durante la generazione. Per favore, riprova più tardi.'
            })
            yield f"data: {err_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/sessions/{session_id}/messages/with-files", response_model=ChatMessageResponse)
async def send_message_with_files(
    session_id: uuid.UUID,
    content: str = Form(""),
    files: list[UploadFile] = File(...),
    current_user: AuthUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_session),
):
    """Send a message with file attachments. Files are referenced in the LLM prompt."""
    result = await db_session.execute(
        select(ChatSessionModel).where(
            ChatSessionModel.id == session_id,
            ChatSessionModel.user_id == uuid.UUID(current_user.user_id),
        )
    )
    chat_model = result.scalar_one_or_none()
    if chat_model is None:
        raise HTTPException(status_code=404, detail="Session not found")

    user_msg = ChatMessageModel(
        id=uuid.uuid4(),
        session_id=session_id,
        role="user",
        content=content or "[File allegato]",
        action_type="file_attachment",
        source_refs=[{"filename": f.filename, "content_type": f.content_type} for f in files],
    )
    db_session.add(user_msg)
    try:
        await db_session.flush()
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Database constraint violation",
        )

    if len(files) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Too many attachments (max 10 per message)",
        )

    file_contexts = []
    for file in files:
        name = file.filename or "attachment"
        try:
            file_bytes = await file.read()
            if len(file_bytes) > 10 * 1024 * 1024:  # 10 MB limit for chat attachments
                file_contexts.append(f"File: {name} (too large, skipped)")
                continue
            # Persist + index the attachment into the corpus so it is
            # reusable in future messages, not just this turn.
            parsed_text = await _ingest_chat_attachment(
                db_session, name,
                file_bytes, file.content_type, chat_model.document_id,
            )
            inline = parsed_text or file_bytes.decode("utf-8", errors="replace")
            file_contexts.append(f"File: {name}\nContent:\n{inline[:2000]}")
        except Exception:
            file_contexts.append(f"File: {name} (could not read content)")

    document_context, doc_model = await _build_chat_context(
        db_session, chat_model, current_user
    )

    file_section = ""
    if file_contexts:
        file_section = "\n\n---\nFile allegati:\n" + "\n---\n".join(file_contexts)

    system_prompt = "\n".join([
        "Sei un assistente per la stesura e revisione di documenti professionali.",
        document_context,
        file_section,
        "Rispondi sempre in italiano. Per informazioni sui documenti caricati usa gli"
        " strumenti search_corpus / list_documents. Cita le fonti quando possibile.",
        "Restituisci SOLO JSON valido: {\"reply\":\"...\",\"action\":null,\"sources\":[]}.",
    ])

    provider = get_llm_provider()
    executor = _make_corpus_executor(db_session)
    user_text = f"Messaggio utente: {content or 'Analizza i file allegati.'}"
    result_data = await _generate_chat_reply(provider, system_prompt, user_text, executor)

    ai_content = result_data.get("reply", "")
    actions = []
    action_data = result_data.get("action")

    # Fix 4: Try to extract action from reply text if not in structured field
    if not action_data:
        extracted = extract_action_from_reply(ai_content)
        if extracted:
            action_data = extracted
            # Remove extracted JSON from visible reply text
            try:
                start = ai_content.find("{")
                end = ai_content.rfind("}")
                if start != -1 and end != -1:
                    candidate = ai_content[start:end + 1]
                    json.loads(candidate)  # verify it's valid JSON
                    cleaned = (ai_content[:start] + ai_content[end + 1:]).strip()
                    ai_content = cleaned or "Ho elaborato la richiesta."
            except (json.JSONDecodeError, Exception):
                pass

    if action_data and isinstance(action_data, dict):
        actions = [{
            "action": action_data.get("type"),
            "label": action_data.get("label", ""),
            "payload": action_data.get("params", {}),
        }]

    # Fix 5: Execute draft action via shared helper
    draft_id = None
    doc_content = None
    if action_data and action_data.get("type") == "draft":
        draft_id, doc_content, draft_actions = await _execute_draft_action(
            action_data, session_id, doc_model, current_user, db_session
        )
        if draft_actions:
            actions = draft_actions

    # Fix 5: Apply draft content to document if a document is open
    if draft_id and doc_model is not None and doc_content is not None:
        try:
            doc_model.content = doc_content
            await db_session.flush()
        except Exception:
            logger.exception("Failed to apply draft content to document")

    if not actions:
        assistant_count = await db_session.scalar(
            select(func.count()).where(
                ChatMessageModel.session_id == session_id,
                ChatMessageModel.role == "assistant",
            )
        ) or 0
        if assistant_count == 0:
            actions = [
                {"action": "suggest_draft", "label": "Genera bozza", "payload": {}},
                {"action": "suggest_patches", "label": "Proponi modifiche", "payload": {}},
            ]

    ai_msg = ChatMessageModel(
        id=uuid.uuid4(),
        session_id=session_id,
        role="assistant",
        content=ai_content,
        actions=actions,
    )
    db_session.add(ai_msg)
    try:
        await db_session.flush()
    except SQLAlchemyError:
        logger.exception("Failed to persist assistant message for session %s", session_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to persist assistant message",
        )
    return ChatMessageResponse.model_validate(ai_msg)


@router.patch("/sessions/{session_id}", response_model=ChatSessionResponse)
async def update_chat_session(
    session_id: uuid.UUID,
    body: SessionUpdate,
    current_user: AuthUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_session),
):
    result = await db_session.execute(
        select(ChatSessionModel).where(
            ChatSessionModel.id == session_id,
            ChatSessionModel.user_id == uuid.UUID(current_user.user_id),
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    if body.title is not None:
        model.title = body.title
    try:
        await db_session.flush()
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Database constraint violation",
        )
    return ChatSessionResponse.model_validate(model)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_session(
    session_id: uuid.UUID,
    current_user: AuthUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_session),
):
    result = await db_session.execute(
        select(ChatSessionModel).where(
            ChatSessionModel.id == session_id,
            ChatSessionModel.user_id == uuid.UUID(current_user.user_id),
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    model.status = "archived"
    try:
        await db_session.flush()
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Database constraint violation",
        )
