import uuid
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.minio.storage import MinioStorageAdapter
from adapters.parsers.docx import parse_docx_bytes
from adapters.parsers.pdf import parse_pdf_bytes
from adapters.postgresql.base import get_session
from adapters.postgresql.models import SourceDocumentModel, TenantModel
from adapters.postgresql.repositories import DocumentRepository
from api.middleware.auth import AuthUser, get_current_user
from api.schemas.document import (
    DocumentCreate,
    DocumentListResponse,
    DocumentResponse,
    DocumentUpdate,
)
from core.models.document import Document

router = APIRouter(prefix="/documents", tags=["documents"])


def _sections_to_prosemirror(sections) -> dict:
    content = []
    for section in sections:
        if section.heading:
            content.append({
                "type": "heading",
                "attrs": {"level": 1},
                "content": [{"type": "text", "text": section.heading}],
            })
        for line in section.content.split("\n"):
            stripped = line.strip()
            if stripped:
                content.append({
                    "type": "paragraph",
                    "content": [{"type": "text", "text": stripped}],
                })
    return {"type": "doc", "content": content}


def _text_to_prosemirror(text: str) -> dict:
    content = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped:
            content.append({
                "type": "paragraph",
                "content": [{"type": "text", "text": stripped}],
            })
    return {"type": "doc", "content": content}


def _parse_to_prosemirror(data: bytes, extension: str) -> dict:
    if extension == ".pdf":
        parsed = parse_pdf_bytes(data)
        return _sections_to_prosemirror(parsed.sections)
    if extension == ".docx":
        parsed = parse_docx_bytes(data)
        return _sections_to_prosemirror(parsed.sections)
    text = data.decode("utf-8", errors="replace")
    return _text_to_prosemirror(text)


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    repo = DocumentRepository(session)
    items, total = await repo.get_by_tenant(current_user.tenant_id, page, per_page)
    return DocumentListResponse(
        data=[DocumentResponse.model_validate(d) for d in items],
        meta={"page": page, "per_page": per_page, "total": total},
    )


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    body: DocumentCreate,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(TenantModel).where(TenantModel.id == UUID(current_user.tenant_id))
    )
    tenant = result.scalar_one_or_none()
    if not tenant or tenant.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant is not active",
        )

    repo = DocumentRepository(session)
    doc = Document(
        tenant_id=current_user.tenant_id,
        title=body.title,
        doc_type=body.doc_type,
        created_by=current_user.user_id,
    )
    model = await repo.create(doc, content={})
    return DocumentResponse.model_validate(model)


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    allowed_extensions = {".pdf", ".docx", ".txt", ".md"}

    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'",
        )

    file_bytes = await file.read()

    result = await session.execute(
        select(TenantModel).where(TenantModel.id == UUID(current_user.tenant_id))
    )
    tenant = result.scalar_one_or_none()
    if not tenant or tenant.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant is not active",
        )

    try:
        prosemirror_content = _parse_to_prosemirror(file_bytes, ext)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse file: {e}",
        )

    doc_uuid = uuid.uuid4()
    doc_type = ext.lstrip(".")
    title = Path(file.filename).stem
    storage = MinioStorageAdapter()
    minio_path = f"source/{doc_uuid}/{file.filename}"

    try:
        await storage.upload(
            path=minio_path,
            data=file_bytes,
            content_type=file.content_type or "application/octet-stream",
            tenant_id=current_user.tenant_id,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to store file: {e}",
        )

    repo = DocumentRepository(session)
    doc = Document(
        tenant_id=current_user.tenant_id,
        title=title,
        doc_type=doc_type,
        created_by=current_user.user_id,
    )
    doc_model = await repo.create(doc, content=prosemirror_content)

    source = SourceDocumentModel(
        tenant_id=UUID(current_user.tenant_id),
        document_id=doc_model.id,
        filename=file.filename,
        doc_type=doc_type,
        file_key=minio_path,
        parsed_content=prosemirror_content,
    )
    session.add(source)
    await session.flush()

    return DocumentResponse.model_validate(doc_model)


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: str,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    repo = DocumentRepository(session)
    model = await repo.get_by_id(doc_id, current_user.tenant_id)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return DocumentResponse.model_validate(model)


@router.patch("/{doc_id}", response_model=DocumentResponse)
async def update_document(
    doc_id: str,
    body: DocumentUpdate,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    repo = DocumentRepository(session)
    data = body.model_dump(exclude_unset=True)
    model = await repo.update(doc_id, current_user.tenant_id, data)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return DocumentResponse.model_validate(model)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    doc_id: str,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    repo = DocumentRepository(session)
    deleted = await repo.delete(doc_id, current_user.tenant_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
