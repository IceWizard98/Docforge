import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.postgresql.base import get_session
from adapters.postgresql.models import TemplateModel
from api.middleware.auth import AuthUser, get_current_user

router = APIRouter(prefix="/templates", tags=["templates"])


class TemplateCreate(BaseModel):
    name: str
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


@router.post("", response_model=TemplateDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    body: TemplateCreate,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    model = TemplateModel(
        id=uuid.uuid4(),
        tenant_id=UUID(current_user.tenant_id),
        name=body.name,
        description=body.description,
        doc_type=body.doc_type,
        content=body.content,
        category=body.category,
        is_public=body.is_public,
    )
    session.add(model)
    await session.flush()
    return TemplateDetailResponse(
        id=model.id,
        name=model.name,
        description=model.description,
        doc_type=model.doc_type,
        category=model.category,
        is_public=model.is_public,
        created_at=model.created_at.isoformat() if model.created_at else "",
        updated_at=model.updated_at.isoformat() if model.updated_at else "",
        content=model.content,
    )


@router.get("", response_model=list[TemplateResponse])
async def list_templates(
    category: str | None = Query(default=None),
    doc_type: str | None = Query(default=None),
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    query = select(TemplateModel).where(
        or_(
            TemplateModel.tenant_id == UUID(current_user.tenant_id),
            TemplateModel.is_public.is_(True),
        )
    )
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
            created_at=r.created_at.isoformat() if r.created_at else "",
            updated_at=r.updated_at.isoformat() if r.updated_at else "",
        )
        for r in rows
    ]


@router.get("/{template_id}", response_model=TemplateDetailResponse)
async def get_template(
    template_id: str,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    query = select(TemplateModel).where(
        TemplateModel.id == UUID(template_id),
        or_(
            TemplateModel.tenant_id == UUID(current_user.tenant_id),
            TemplateModel.is_public.is_(True),
        ),
    )
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
        created_at=model.created_at.isoformat() if model.created_at else "",
        updated_at=model.updated_at.isoformat() if model.updated_at else "",
        content=model.content,
    )
