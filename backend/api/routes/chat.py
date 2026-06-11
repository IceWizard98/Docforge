import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.postgresql.base import get_session
from adapters.postgresql.models import ChatMessageModel, ChatSessionModel
from api.middleware.auth import AuthUser, get_current_user
from api.schemas.chat import (
    ChatMessageRequest,
    ChatMessageResponse,
    ChatSessionCreate,
    ChatSessionDetailResponse,
    ChatSessionListResponse,
    ChatSessionResponse,
)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    body: ChatSessionCreate,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    chat_id = uuid.uuid4()
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
    page: int = 1,
    per_page: int = 20,
    current_user: AuthUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_session),
):
    from sqlalchemy import func

    tid = uuid.UUID(current_user.tenant_id)
    base = select(ChatSessionModel).where(ChatSessionModel.tenant_id == tid)
    total = await db_session.scalar(select(func.count()).select_from(base.subquery())) or 0
    offset = (page - 1) * per_page
    result = await db_session.execute(
        base.order_by(ChatSessionModel.updated_at.desc()).offset(offset).limit(per_page)
    )
    models = list(result.scalars().all())
    return ChatSessionListResponse(
        data=[ChatSessionResponse.model_validate(m) for m in models],
        meta={"page": page, "per_page": per_page, "total": total},
    )


@router.get("/sessions/{session_id}", response_model=ChatSessionDetailResponse)
async def get_session(
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

    import json

    ai_content = (
        "I acknowledge receipt of your message regarding the document. "
        "Your input has been processed and integrated into the drafting context."
    )
    ai_msg = ChatMessageModel(
        id=uuid.uuid4(),
        session_id=uuid.UUID(session_id),
        role="assistant",
        content=ai_content,
        actions=json.dumps([
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
        ]),
    )
    db_session.add(ai_msg)
    await db_session.flush()
    return ChatMessageResponse.model_validate(ai_msg)
