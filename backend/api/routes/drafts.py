from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.postgresql.base import get_session
from adapters.postgresql.models import DraftModel
from api.middleware.auth import AuthUser, get_current_user
from api.schemas.drafts import DraftCreate, DraftResponse, SectionRegenerateRequest

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


@router.post("/{draft_id}/sections/{section_id}/regenerate", response_model=DraftResponse)
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

    content = dict(model.content) if model.content else {}
    sections = content.get("sections", [])
    updated = False
    for sec in sections:
        if sec.get("section_id") == section_id:
            sec["status"] = "regenerating"
            updated = True
            break
    if not updated:
        sections.append({"section_id": section_id, "status": "regenerating", "content": ""})
    content["sections"] = sections
    model.content = content
    await session.flush()
    return DraftResponse.model_validate(model)
