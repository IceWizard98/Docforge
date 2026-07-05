import asyncio
import logging
import uuid
from io import BytesIO
from pathlib import Path
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.minio.storage import MinioStorageAdapter
from adapters.postgresql.base import get_session
from adapters.postgresql.models import TemplateModel
from api.middleware.auth import AuthUser, get_current_user
from api.upload_validation import read_validated_upload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/templates", tags=["templates"])

DOCX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


def _iso(dt) -> str:
    if not dt:
        return ""
    return dt.isoformat() if hasattr(dt, "isoformat") else str(dt)


class TemplateCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None
    doc_type: str | None = None
    # optional: metadata-only templates (the DOCX file is the payload for uploads)
    content: dict = Field(default_factory=dict)
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
    has_file: bool
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


def _to_response(m: TemplateModel) -> TemplateResponse:
    return TemplateResponse(
        id=m.id,
        name=m.name,
        description=m.description,
        doc_type=m.doc_type,
        category=m.category,
        is_public=m.is_public,
        has_file=bool(m.file_key),
        created_at=_iso(m.created_at),
        updated_at=_iso(m.updated_at),
    )


def _to_detail(m: TemplateModel) -> TemplateDetailResponse:
    return TemplateDetailResponse(**_to_response(m).model_dump(), content=m.content)


@router.post("", response_model=TemplateDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    body: TemplateCreate,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    # Only admins may publish to the shared public library (it's served to every
    # user and seeds documents); a non-admin's template is forced private.
    is_public = bool(body.is_public) and current_user.role == "admin"
    model = TemplateModel(
        id=uuid.uuid4(),
        name=body.name,
        description=body.description,
        doc_type=body.doc_type,
        content=body.content,
        category=body.category,
        is_public=is_public,
        created_by=uuid.UUID(current_user.user_id),
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
    return _to_detail(model)


@router.post("/upload", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def upload_template(  # noqa: PLR0913
    file: UploadFile = File(...),
    name: str = Form(..., min_length=1),
    description: str | None = Form(default=None),
    doc_type: str | None = Form(default=None),
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Upload a .docx template. The file is stored in MinIO and owned by the caller;
    the DB row's `content` stays empty ({}) — the DOCX itself is the payload."""
    _, data = await read_validated_upload(
        file, {".docx"}, bad_request_status=status.HTTP_422_UNPROCESSABLE_ENTITY
    )

    # Verify the bytes are a real, openable DOCX before we store or record anything.
    # python-docx parsing is CPU-bound and synchronous; run it off the event loop
    # so a large/pathological file can't freeze the single uvicorn loop (which would
    # stall every other in-flight request — chat, saves, auth).
    from docx import Document

    try:
        await asyncio.to_thread(Document, BytesIO(data))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="file DOCX non valido"
        )

    template_id = uuid.uuid4()
    # Path(...).name strips any directory components so a crafted filename can't
    # escape the per-template key prefix.
    safe_filename = Path(file.filename).name
    file_key = f"templates/{template_id}/{safe_filename}"
    storage = MinioStorageAdapter()
    try:
        stored_key = await storage.upload(file_key, data, DOCX_CONTENT_TYPE)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Failed to store file: {e}"
        )

    model = TemplateModel(
        id=template_id,
        name=name,
        description=description,
        doc_type=doc_type,
        content={},
        category=None,
        is_public=False,
        file_key=stored_key,
        created_by=uuid.UUID(current_user.user_id),
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
    return _to_response(model)


@router.get("", response_model=list[TemplateResponse])
async def list_templates(
    category: str | None = Query(default=None),
    doc_type: str | None = Query(default=None),
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    # Visible templates: the shared public library plus the caller's own private ones.
    owner = uuid.UUID(current_user.user_id)
    query = select(TemplateModel).where(
        or_(TemplateModel.is_public.is_(True), TemplateModel.created_by == owner)
    )
    if category:
        query = query.where(TemplateModel.category == category)
    if doc_type:
        query = query.where(TemplateModel.doc_type == doc_type)
    query = query.order_by(TemplateModel.updated_at.desc())

    result = await session.execute(query)
    rows = result.scalars().all()
    return [_to_response(r) for r in rows]


@router.get("/{template_id}", response_model=TemplateDetailResponse)
async def get_template(
    template_id: UUID,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    owner = uuid.UUID(current_user.user_id)
    query = select(TemplateModel).where(
        TemplateModel.id == template_id,
        or_(TemplateModel.is_public.is_(True), TemplateModel.created_by == owner),
    )
    result = await session.execute(query)
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return _to_detail(model)


@router.patch("/{template_id}", response_model=TemplateDetailResponse)
async def update_template(
    template_id: UUID,
    body: TemplateUpdate,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    owner = uuid.UUID(current_user.user_id)
    result = await session.execute(
        select(TemplateModel).where(TemplateModel.id == template_id)
    )
    model = result.scalar_one_or_none()
    # Only the owner may mutate. A non-owner (or a legacy ownerless public template)
    # is indistinguishable from "not found" so we don't leak existence.
    if model is None or model.created_by != owner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    data = body.model_dump(exclude_unset=True)
    # Publishing to the shared library stays admin-only, mirroring create.
    if "is_public" in data:
        data["is_public"] = bool(data["is_public"]) and current_user.role == "admin"
    for field, value in data.items():
        setattr(model, field, value)

    try:
        await session.flush()
    except SQLAlchemyError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Database constraint violation",
        ) from exc
    return _to_detail(model)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: UUID,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    owner = uuid.UUID(current_user.user_id)
    result = await session.execute(
        select(TemplateModel).where(TemplateModel.id == template_id)
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    if model.created_by is not None:
        if model.created_by != owner:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    # A legacy public template without an owner is deletable only by an admin.
    elif current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    if model.file_key:
        storage = MinioStorageAdapter()
        try:
            await storage.delete(model.file_key)
        except Exception:
            logger.warning("Failed to delete stored file for template %s", model.id)

    await session.delete(model)
    try:
        await session.flush()
    except SQLAlchemyError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Failed to delete template"
        )
