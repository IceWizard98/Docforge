import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.llm.factory import get_llm_provider
from adapters.postgresql.base import get_session
from adapters.postgresql.models import DocumentModel
from api.middleware.auth import AuthUser, get_current_user
from api.schemas.validation import ValidationReport
from core.services.validation import ValidationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["validation"])


@router.post("/{doc_id}/validate", response_model=ValidationReport)
async def validate_document(
    doc_id: UUID,
    llm: bool = Query(False, description="Enable LLM-based semantic validation"),
    spec: str | None = Query(None, description="Optional JSON spec for section audit"),
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    import json

    result = await session.execute(
        select(DocumentModel).where(
            DocumentModel.id == doc_id,
            DocumentModel.created_by == UUID(current_user.user_id),
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

    spec_parsed: dict | None = None
    if spec:
        try:
            spec_parsed = json.loads(spec)
        except json.JSONDecodeError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid spec JSON")

    service = ValidationService()
    report = await service.validate_document_full(doc_dict, spec_parsed)

    if llm:
        try:
            provider = get_llm_provider()
            llm_issues = await service.validate_with_llm(doc_dict, provider)
            report["issues"].extend(llm_issues)
            report["llm_issues"] = llm_issues
            report["summary"] = (
                f"{report['summary']} | "
                f"{len(llm_issues)} LLM issues"
            )
        except Exception:
            logger.exception("LLM validation unavailable for doc %s", doc_id)

    doc.status = "in_review"
    try:
        await session.flush()
    except SQLAlchemyError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Validation conflict, please retry",
        )

    return ValidationReport(
        document_id=str(doc_id),
        version=doc.version,
        passed=report["passed"],
        score=report["score"],
        issues=report["issues"],
        summary=report["summary"],
        issues_grouped=report.get("issues_grouped"),
    )


@router.get("/{doc_id}/validation", response_model=ValidationReport)
async def get_validation(
    doc_id: UUID,
    llm: bool = Query(False, description="Enable LLM-based semantic validation"),
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):

    result = await session.execute(
        select(DocumentModel).where(
            DocumentModel.id == doc_id,
            DocumentModel.created_by == UUID(current_user.user_id),
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
    report = await service.validate_document_full(doc_dict)

    if llm:
        try:
            provider = get_llm_provider()
            llm_issues = await service.validate_with_llm(doc_dict, provider)
            report["issues"].extend(llm_issues)
            report["llm_issues"] = llm_issues
            report["summary"] = (
                f"{report['summary']} | "
                f"{len(llm_issues)} LLM issues"
            )
        except Exception:
            logger.exception("LLM validation unavailable for doc %s", doc_id)

    return ValidationReport(
        document_id=str(doc_id),
        version=doc.version,
        passed=report["passed"],
        score=report["score"],
        issues=report["issues"],
        summary=report["summary"],
        issues_grouped=report.get("issues_grouped"),
    )
