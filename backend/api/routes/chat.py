import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.llm.factory import get_llm_provider
from adapters.postgresql.base import get_session
from adapters.postgresql.models import ChatMessageModel, ChatSessionModel, DocumentModel
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


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
                DocumentModel.id == uuid.UUID(body.document_id),
                DocumentModel.tenant_id == uuid.UUID(current_user.tenant_id),
            )
        )
        if doc_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )

    model = ChatSessionModel(
        id=chat_id,
        tenant_id=uuid.UUID(current_user.tenant_id) if current_user.tenant_id else None,
        document_id=uuid.UUID(body.document_id) if body.document_id else None,
        user_id=uuid.UUID(current_user.user_id),
        title=body.title,
        context_type=body.context_type,
    )
    session.add(model)
    await session.flush()
    return ChatSessionResponse.model_validate(model)


@router.get("/sessions", response_model=ChatSessionListResponse)
async def list_sessions(
    document_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    current_user: AuthUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_session),
):
    tid = uuid.UUID(current_user.tenant_id)
    base = select(ChatSessionModel).where(ChatSessionModel.tenant_id == tid)

    if document_id:
        base = base.where(ChatSessionModel.document_id == uuid.UUID(document_id))

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
                tenant_id=m.tenant_id,
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
    session_id: str,
    current_user: AuthUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_session),
):
    result = await db_session.execute(
        select(ChatSessionModel).where(
            ChatSessionModel.id == uuid.UUID(session_id),
            ChatSessionModel.tenant_id == uuid.UUID(current_user.tenant_id),
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


@router.post("/sessions/{session_id}/messages", response_model=ChatMessageResponse)
async def send_message(
    session_id: str,
    body: ChatMessageRequest,
    current_user: AuthUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_session),
):
    result = await db_session.execute(
        select(ChatSessionModel).where(
            ChatSessionModel.id == uuid.UUID(session_id),
            ChatSessionModel.tenant_id == uuid.UUID(current_user.tenant_id),
        )
    )
    chat_model = result.scalar_one_or_none()
    if chat_model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    user_msg = ChatMessageModel(
        id=uuid.uuid4(),
        session_id=uuid.UUID(session_id),
        role="user",
        content=body.content,
    )
    db_session.add(user_msg)
    await db_session.flush()

    document_context = ""
    if chat_model.document_id:
        doc_result = await db_session.execute(
            select(DocumentModel).where(DocumentModel.id == chat_model.document_id)
        )
        doc_model = doc_result.scalar_one_or_none()
        if doc_model:
            doc_content_preview = json.dumps(doc_model.content)[:3000] if doc_model.content else ""
            document_context = f"""Document context:
Title: {doc_model.title}
Type: {doc_model.doc_type}
Content (first 3000 chars):
{doc_content_preview}"""

    msg_result = await db_session.execute(
        select(ChatMessageModel)
        .where(ChatMessageModel.session_id == uuid.UUID(session_id))
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
        "Sei un assistente per la stesura e revisione di documenti professionali.",
        "",
        document_context,
        "",
        "Chat history (ultimi messaggi):",
        history,
        "",
        "Il tuo compito è aiutare l'utente con la creazione, modifica e validazione di documenti.",
        "Puoi proporre le seguenti azioni:",
        '- "draft": genera una nuova bozza di documento',
        '- "suggest_edit": suggerisce modifiche al documento corrente',
        '- "validate": valida il documento o una sua sezione',
        '- "answer_question": risponde a domande senza proporre azioni specifiche',
        "",
        "Rispondi sempre in italiano.",
        'Restituisci la risposta in formato JSON valido con la seguente struttura:',
        '{',
        '  "reply": "Testo della risposta...",',
        '  "action": null | {"type": "...", "label": "...", "params": {}},',
        '  "sources": [{"doc_id": "...", "chunk_id": null, "snippet": null, "confidence": 0.0}]',
        '}',
    ]
    system_prompt = "\n".join(system_prompt_parts)

    prompt = f"{system_prompt}\n\nMessaggio utente: {body.content}"

    try:
        provider = get_llm_provider()
        result_data = await provider.generate_structured(prompt, dict)
    except Exception:
        logger.exception("LLM generation failed for session %s", session_id)
        result_data = {
            "reply": "Mi dispiace, si è verificato un errore durante l'elaborazione.",
            "action": None,
            "sources": [],
        }

    ai_content = result_data.get("reply", "")

    action_data = result_data.get("action")
    actions = []
    if action_data and isinstance(action_data, dict):
        action_type = action_data.get("type")
        actions = [{
            "action": action_type,
            "label": action_data.get("label", ""),
            "payload": action_data.get("params", {}),
        }]

    if not actions:
        actions = [
            {
                "action": "suggest_draft",
                "label": "Genera bozza",
                "payload": {"session_id": session_id},
            },
            {
                "action": "suggest_patches",
                "label": "Proponi modifiche",
                "payload": {"session_id": session_id},
            },
        ]

    sources = result_data.get("sources", [])

    ai_msg = ChatMessageModel(
        id=uuid.uuid4(),
        session_id=uuid.UUID(session_id),
        role="assistant",
        content=ai_content,
        actions=actions,
        sources=sources or [],
    )
    db_session.add(ai_msg)
    await db_session.flush()
    return ChatMessageResponse.model_validate(ai_msg)


@router.patch("/sessions/{session_id}", response_model=ChatSessionResponse)
async def update_chat_session(
    session_id: str,
    body: SessionUpdate,
    current_user: AuthUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_session),
):
    result = await db_session.execute(
        select(ChatSessionModel).where(
            ChatSessionModel.id == uuid.UUID(session_id),
            ChatSessionModel.tenant_id == uuid.UUID(current_user.tenant_id),
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    if body.title is not None:
        model.title = body.title
    await db_session.flush()
    return ChatSessionResponse.model_validate(model)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_session(
    session_id: str,
    current_user: AuthUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_session),
):
    result = await db_session.execute(
        select(ChatSessionModel).where(
            ChatSessionModel.id == uuid.UUID(session_id),
            ChatSessionModel.tenant_id == uuid.UUID(current_user.tenant_id),
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    model.status = "archived"
    await db_session.flush()
