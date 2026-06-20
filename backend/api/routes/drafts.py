import logging
import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from adapters.postgresql.base import get_session
from adapters.postgresql.models import ChatMessageModel, ChatSessionModel, DraftModel
from adapters.postgresql.repositories import DocumentRepository
from api.middleware.auth import AuthUser, get_current_user
from api.schemas.document import DocumentResponse
from api.schemas.drafts import DraftCreate, DraftResponse, SectionRegenerateRequest
from core.models.document import Document
from workers.drafting import generate_draft_task, generate_section_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/drafts", tags=["drafts"])


@router.post("", response_model=DraftResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_draft(
    body: DraftCreate,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):

    chat_result = await session.execute(
        select(ChatSessionModel).where(
            ChatSessionModel.id == body.chat_session_id,
            ChatSessionModel.user_id == uuid.UUID(current_user.user_id),
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
        chat_session_id=body.chat_session_id,
        document_id=body.document_id,
        title="Draft",
        spec={
            "chat_session_id": str(body.chat_session_id),
            "sections": [],
        },
        status="generating",
        progress={"total_sections": 0, "completed_sections": 0},
    )
    session.add(model)
    try:
        await session.flush()
    except SQLAlchemyError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A draft with the given parameters already exists",
        )

    msg_result = await session.execute(
        select(ChatMessageModel)
        .where(ChatMessageModel.session_id == body.chat_session_id)
        .order_by(ChatMessageModel.created_at)
    )
    messages = [
        {"role": m.role, "content": m.content}
        for m in msg_result.scalars().all()
    ]
    generate_draft_task.apply_async(
        (
            str(body.chat_session_id),
            messages,
            str(body.document_id) if body.document_id is not None else None,
        ),
        countdown=2,
    )
    logger.info(
        "Draft %s generation dispatched for session %s by user %s",
        str(draft_id), body.chat_session_id, current_user.user_id,
    )
    return DraftResponse.model_validate(model)


@router.get("/{draft_id}", response_model=DraftResponse)
async def get_draft(
    draft_id: UUID,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):

    result = await session.execute(
        select(DraftModel)
        .join(ChatSessionModel, DraftModel.chat_session_id == ChatSessionModel.id)
        .where(
            DraftModel.id == draft_id,
            ChatSessionModel.user_id == uuid.UUID(current_user.user_id),
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    return DraftResponse.model_validate(model)


@router.post("/{draft_id}/sections/{section_id}/regenerate", status_code=status.HTTP_202_ACCEPTED)
async def regenerate_section(
    draft_id: UUID,
    section_id: UUID,
    body: SectionRegenerateRequest,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):

    result = await session.execute(
        select(DraftModel)
        .join(ChatSessionModel, DraftModel.chat_session_id == ChatSessionModel.id)
        .where(
            DraftModel.id == draft_id,
            ChatSessionModel.user_id == uuid.UUID(current_user.user_id),
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")

    generate_section_task.delay(
        draft_id=str(model.id),
        section_id=str(section_id),
        spec=dict(model.spec or {}),
        context_pack={},
    )
    logger.info(
        "Section %s regeneration dispatched for draft %s by user %s",
        section_id, draft_id, current_user.user_id,
    )
    return {"status": "dispatched", "message": "Section regeneration dispatched"}


@router.post("/{draft_id}/promote", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def promote_draft(
    draft_id: UUID,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Promote a completed draft to a permanent document."""
    result = await session.execute(
        select(DraftModel)
        .join(ChatSessionModel, DraftModel.chat_session_id == ChatSessionModel.id)
        .where(
            DraftModel.id == draft_id,
            ChatSessionModel.user_id == uuid.UUID(current_user.user_id),
        )
    )
    draft = result.scalar_one_or_none()
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")

    if draft.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Draft not ready for promotion (status: {draft.status})",
        )

    spec = draft.spec or {}
    title = spec.get("title") or draft.title
    doc_type = spec.get("doc_type") or ""

    doc = Document(
        title=title,
        doc_type=doc_type,
        created_by=current_user.user_id,
    )
    repo = DocumentRepository(session)
    doc_model = await repo.create(doc, draft.content or {})

    draft.document_id = doc_model.id
    draft.status = "promoted"
    try:
        await session.flush()
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Promotion failed due to database conflict",
        )

    return DocumentResponse.model_validate(doc_model)


class SectionUpdateRequest(BaseModel):
    content: dict | None = None
    title: str | None = None


@router.patch("/{draft_id}/sections/{section_id}", status_code=status.HTTP_200_OK)
async def update_draft_section(
    draft_id: UUID,
    section_id: str,
    body: SectionUpdateRequest,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update a specific section within a draft."""
    result = await session.execute(
        select(DraftModel)
        .join(ChatSessionModel, DraftModel.chat_session_id == ChatSessionModel.id)
        .where(
            DraftModel.id == draft_id,
            ChatSessionModel.user_id == uuid.UUID(current_user.user_id),
        )
    )
    draft = result.scalar_one_or_none()
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")

    draft_content = draft.content or {}
    sections = draft_content.get("content", [])

    found = False
    for section in sections:
        attrs = section.get("attrs", {}) if isinstance(section, dict) else {}
        if attrs.get("sectionId") == section_id or section.get("section_id") == section_id:
            if body.content is not None:
                section["content"] = body.content.get("content", body.content)
            if body.title is not None and isinstance(section.get("attrs"), dict):
                section["attrs"]["title"] = body.title
            found = True
            break

    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found in draft")

    flag_modified(draft, "content")
    try:
        await session.flush()
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Failed to update draft section",
        )

    return {"status": "updated", "draft_id": str(draft_id), "section_id": section_id}
