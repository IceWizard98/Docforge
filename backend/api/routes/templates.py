import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.postgresql.base import get_session
from adapters.postgresql.models import TemplateModel
from api.middleware.auth import AuthUser, get_current_user

router = APIRouter(prefix="/templates", tags=["templates"])


def _iso(dt) -> str:
    if not dt:
        return ""
    return dt.isoformat() if hasattr(dt, "isoformat") else str(dt)


class TemplateCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None
    doc_type: str | None = None
    content: dict
    category: str | None = None
    is_public: bool = False


class TemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    doc_type: str | None
    category: str | None
    is_public: bool
    created_at: str
    updated_at: str


class TemplateDetailResponse(TemplateResponse):
    content: dict


class TemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    description: str | None = None
    doc_type: str | None = None
    content: dict | None = None
    category: str | None = None
    is_public: bool | None = None


@router.post("", response_model=TemplateDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    body: TemplateCreate,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    model = TemplateModel(
        id=uuid.uuid4(),
        name=body.name,
        description=body.description,
        doc_type=body.doc_type,
        content=body.content,
        category=body.category,
        is_public=body.is_public,
    )
    session.add(model)
    try:
        await session.flush()
    except SQLAlchemyError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Database constraint violation",
        ) from exc
    return TemplateDetailResponse(
        id=model.id,
        name=model.name,
        description=model.description,
        doc_type=model.doc_type,
        category=model.category,
        is_public=model.is_public,
        created_at=_iso(model.created_at),
        updated_at=_iso(model.updated_at),
        content=model.content,
    )


@router.get("", response_model=list[TemplateResponse])
async def list_templates(
    category: str | None = Query(default=None),
    doc_type: str | None = Query(default=None),
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    query = select(TemplateModel)
    if category:
        query = query.where(TemplateModel.category == category)
    if doc_type:
        query = query.where(TemplateModel.doc_type == doc_type)
    query = query.order_by(TemplateModel.updated_at.desc())

    result = await session.execute(query)
    rows = result.scalars().all()
    return [
        TemplateResponse(
            id=r.id,
            name=r.name,
            description=r.description,
            doc_type=r.doc_type,
            category=r.category,
            is_public=r.is_public,
            created_at=_iso(r.created_at),
            updated_at=_iso(r.updated_at),
        )
        for r in rows
    ]


@router.get("/{template_id}", response_model=TemplateDetailResponse)
async def get_template(
    template_id: UUID,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    query = select(TemplateModel).where(TemplateModel.id == template_id)
    result = await session.execute(query)
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return TemplateDetailResponse(
        id=model.id,
        name=model.name,
        description=model.description,
        doc_type=model.doc_type,
        category=model.category,
        is_public=model.is_public,
        created_at=_iso(model.created_at),
        updated_at=_iso(model.updated_at),
        content=model.content,
    )


@router.patch("/{template_id}", response_model=TemplateDetailResponse)
async def update_template(
    template_id: UUID,
    body: TemplateUpdate,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(TemplateModel).where(
            TemplateModel.id == template_id,
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    allowed = {"name", "description", "doc_type", "content", "category", "is_public"}
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        if field in allowed:
            setattr(model, field, value)

    try:
        await session.flush()
    except SQLAlchemyError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Database constraint violation",
        ) from exc

    return TemplateDetailResponse(
        id=model.id,
        name=model.name,
        description=model.description,
        doc_type=model.doc_type,
        category=model.category,
        is_public=model.is_public,
        created_at=_iso(model.created_at),
        updated_at=_iso(model.updated_at),
        content=model.content,
    )
