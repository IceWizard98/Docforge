from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.postgresql.base import get_session
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


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    page: int = 1,
    per_page: int = 20,
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
    repo = DocumentRepository(session)
    doc = Document(
        tenant_id=current_user.tenant_id,
        title=body.title,
        doc_type=body.doc_type,
        created_by=current_user.user_id,
    )
    model = await repo.create(doc, content={})
    return DocumentResponse.model_validate(model)


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
