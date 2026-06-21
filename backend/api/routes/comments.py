import uuid
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.postgresql.base import get_session
from adapters.postgresql.models import CommentModel, DocumentModel
from api.middleware.auth import AuthUser, get_current_user


class CommentCreate(BaseModel):
    document_id: UUID
    thread_id: UUID | None = None
    section_id: str | None = None
    clause_id: str | None = None
    content: str


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    thread_id: UUID | None = None
    section_id: str | None = None
    clause_id: str | None = None
    author: str
    content: str
    resolved: bool
    created_at: datetime


router = APIRouter(prefix="/comments", tags=["comments"])


@router.post("", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def create_comment(
    body: CommentCreate,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    doc_result = await session.execute(
        select(DocumentModel).where(
            DocumentModel.id == body.document_id,
        )
    )
    if doc_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Document not found")

    model = CommentModel(
        id=uuid.uuid4(),
        document_id=body.document_id,
        section_id=body.section_id,
        clause_id=body.clause_id,
        thread_id=body.thread_id,
        author=current_user.email or current_user.user_id,
        content=body.content,
    )
    session.add(model)
    try:
        await session.flush()
    except SQLAlchemyError:
        raise HTTPException(status_code=409, detail="Comment conflicts with existing data")
    return CommentResponse.model_validate(model)


@router.get("/document/{document_id}", response_model=list[CommentResponse])
async def list_comments(
    document_id: UUID,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(CommentModel)
        .where(
            CommentModel.document_id == document_id,
        )
        .order_by(CommentModel.created_at)
    )
    return [CommentResponse.model_validate(m) for m in result.scalars().all()]


@router.patch("/{comment_id}/resolve", response_model=CommentResponse)
async def resolve_comment(
    comment_id: UUID,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(CommentModel).where(
            CommentModel.id == comment_id,
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    model.resolved = not model.resolved
    try:
        await session.flush()
    except SQLAlchemyError:
        raise HTTPException(status_code=409, detail="Comment conflicts with existing data")
    return CommentResponse.model_validate(model)
