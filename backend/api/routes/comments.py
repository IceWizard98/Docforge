import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.postgresql.base import get_session
from adapters.postgresql.models import CommentModel, DocumentModel
from api.middleware.auth import AuthUser, get_current_user


class CommentCreate(BaseModel):
    document_id: str
    thread_id: str | None = None
    content: str


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    thread_id: str | None
    author: str
    content: str
    resolved: bool
    created_at: str


router = APIRouter(prefix="/comments", tags=["comments"])


@router.post("", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def create_comment(
    body: CommentCreate,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    doc_result = await session.execute(
        select(DocumentModel).where(
            DocumentModel.id == uuid.UUID(body.document_id),
            DocumentModel.tenant_id == uuid.UUID(current_user.tenant_id),
        )
    )
    if doc_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Document not found")

    model = CommentModel(
        id=uuid.uuid4(),
        tenant_id=uuid.UUID(current_user.tenant_id),
        document_id=uuid.UUID(body.document_id),
        thread_id=uuid.UUID(body.thread_id) if body.thread_id else None,
        author=current_user.email or current_user.user_id,
        content=body.content,
    )
    session.add(model)
    await session.flush()
    return CommentResponse.model_validate(model)


@router.get("/document/{document_id}", response_model=list[CommentResponse])
async def list_comments(
    document_id: str,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(CommentModel)
        .where(
            CommentModel.document_id == uuid.UUID(document_id),
            CommentModel.tenant_id == uuid.UUID(current_user.tenant_id),
        )
        .order_by(CommentModel.created_at)
    )
    return [CommentResponse.model_validate(m) for m in result.scalars().all()]


@router.patch("/{comment_id}/resolve", response_model=CommentResponse)
async def resolve_comment(
    comment_id: str,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(CommentModel).where(
            CommentModel.id == uuid.UUID(comment_id),
            CommentModel.tenant_id == uuid.UUID(current_user.tenant_id),
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    model.resolved = not model.resolved
    await session.flush()
    return CommentResponse.model_validate(model)
