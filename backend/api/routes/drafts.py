import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.postgresql.base import get_session
from adapters.postgresql.models import ChatMessageModel, DraftModel
from api.middleware.auth import AuthUser, get_current_user
from api.schemas.drafts import DraftCreate, DraftResponse, SectionRegenerateRequest
from workers.drafting import generate_draft_task, generate_section_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/drafts", tags=["drafts"])


@router.post("", response_model=DraftResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_draft(
    body: DraftCreate,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    import uuid

    from adapters.postgresql.models import ChatSessionModel

    chat_result = await session.execute(
        select(ChatSessionModel).where(
            ChatSessionModel.id == uuid.UUID(body.chat_session_id),
            ChatSessionModel.tenant_id == uuid.UUID(current_user.tenant_id),
        )
    )
    chat_session = chat_result.scalar_one_or_none()
    if chat_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )

    draft_id = uuid.uuid4()
    model = DraftModel(
        id=draft_id,
        tenant_id=uuid.UUID(current_user.tenant_id),
        chat_session_id=uuid.UUID(body.chat_session_id),
        document_id=uuid.UUID(body.document_id) if body.document_id else None,
        title="Draft",
        spec={"chat_session_id": body.chat_session_id, "sections": []},
        status="generating",
        progress={"total_sections": 0, "completed_sections": 0},
    )
    session.add(model)
    await session.flush()

    msg_result = await session.execute(
        select(ChatMessageModel)
        .where(ChatMessageModel.session_id == uuid.UUID(body.chat_session_id))
        .order_by(ChatMessageModel.created_at)
    )
    messages = [
        {"role": m.role, "content": m.content}
        for m in msg_result.scalars().all()
    ]
    generate_draft_task.delay(
        chat_session_id=body.chat_session_id,
        messages=messages,
        document_id=body.document_id,
    )
    logger.info(
        "Draft %s generation dispatched for session %s by user %s",
        str(draft_id), body.chat_session_id, current_user.user_id,
    )
    return DraftResponse.model_validate(model)


@router.get("/{draft_id}", response_model=DraftResponse)
async def get_draft(
    draft_id: str,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    import uuid

    result = await session.execute(
        select(DraftModel).where(
            DraftModel.id == uuid.UUID(draft_id),
            DraftModel.tenant_id == uuid.UUID(current_user.tenant_id),
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    return DraftResponse.model_validate(model)


@router.post("/{draft_id}/sections/{section_id}/regenerate", status_code=status.HTTP_202_ACCEPTED)
async def regenerate_section(
    draft_id: str,
    section_id: str,
    body: SectionRegenerateRequest,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    import uuid

    result = await session.execute(
        select(DraftModel).where(
            DraftModel.id == uuid.UUID(draft_id),
            DraftModel.tenant_id == uuid.UUID(current_user.tenant_id),
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")

    generate_section_task.delay(
        draft_id=str(model.id),
        section_id=section_id,
        spec=dict(model.spec or {}),
        context_pack={},
    )
    logger.info(
        "Section %s regeneration dispatched for draft %s by user %s",
        section_id, draft_id, current_user.user_id,
    )
    return {"status": "dispatched", "message": "Section regeneration dispatched"}
