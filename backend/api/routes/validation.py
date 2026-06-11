from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.postgresql.base import get_session
from adapters.postgresql.models import DocumentModel
from api.middleware.auth import AuthUser, get_current_user
from api.schemas.validation import ValidationReport
from core.services.validation import ValidationService

router = APIRouter(prefix="/documents", tags=["validation"])


@router.post("/{doc_id}/validate", status_code=status.HTTP_202_ACCEPTED)
async def start_validation(
    doc_id: str,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    import uuid

    result = await session.execute(
        select(DocumentModel).where(
            DocumentModel.id == uuid.UUID(doc_id),
            DocumentModel.tenant_id == uuid.UUID(current_user.tenant_id),
        )
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    doc.status = "in_review"
    await session.flush()
    return {"status": "validation_started", "document_id": doc_id}


@router.get("/{doc_id}/validation", response_model=ValidationReport)
async def get_validation(
    doc_id: str,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    import uuid

    result = await session.execute(
        select(DocumentModel).where(
            DocumentModel.id == uuid.UUID(doc_id),
            DocumentModel.tenant_id == uuid.UUID(current_user.tenant_id),
        )
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    doc_dict = {
        "id": doc_id,
        "version": doc.version,
        "content": doc.content or {},
    }
    service = ValidationService()
    report = await service.validate_document(doc_dict)

    score_norm = max(0.0, report["score"] / 100.0)
    return ValidationReport(
        document_id=doc_id,
        version=doc.version,
        passed=report["passed"],
        score=round(score_norm, 2),
        issues=report["issues"],
        summary=report["summary"],
    )
