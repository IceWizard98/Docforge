import logging
import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from adapters.llm.factory import get_llm_provider
from adapters.postgresql.base import get_session
from adapters.postgresql.models import DocumentModel, PatchSetModel
from api.middleware.auth import AuthUser, get_current_user
from api.schemas.patches import PatchGenerateRequest, PatchSetResponse
from core.services.patching import PatchService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/patches", tags=["patches"])


def _enrich_operations(
    operations: list[dict], patch_set_id: str
) -> list[dict]:
    enriched = []
    for i, op in enumerate(operations or []):
        enriched.append({
            "id": f"op_{uuid.uuid4().hex[:12]}",
            "patch_set_id": patch_set_id,
            "operation": op.get("operation", ""),
            "target_section": op.get("target_section"),
            "target_clause": op.get("target_clause"),
            "target_path": op.get("target_path", []),
            "content": op.get("content"),
            "status": "pending",
            "sort_order": i,
            "rationale": op.get("rationale"),
        })
    return enriched


@router.post("", response_model=PatchSetResponse, status_code=status.HTTP_201_CREATED)
async def generate_patch(
    body: PatchGenerateRequest,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(DocumentModel).where(
            DocumentModel.id == body.document_id,
        )
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    doc_dict = {
        "id": body.document_id,
        "title": doc.title or "",
        "version": doc.version,
        "content": doc.content or {},
    }

    provider = get_llm_provider()
    service = PatchService(llm=provider)
    plan = await service.generate_patch_plan(doc_dict, body.instructions, provider)

    patch_set = PatchSetModel(
        id=uuid.uuid4(),
        document_id=body.document_id,
        version_from=doc.version,
        version_to=doc.version + 1,
        status="proposed",
        summary=plan.get("summary", f"Patch generated from: {body.instructions[:100]}"),
        operations=[],
        created_by=uuid.UUID(current_user.user_id),
    )

    raw_ops = plan.get("operations", [])
    patch_set.operations = _enrich_operations(
        raw_ops, str(patch_set.id)
    )

    session.add(patch_set)
    try:
        await session.flush()
    except SQLAlchemyError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Database constraint violation",
        ) from exc

    return PatchSetResponse(
        id=str(patch_set.id),
        document_id=body.document_id,
        version_from=patch_set.version_from,
        version_to=patch_set.version_to,
        summary=patch_set.summary,
        operations=patch_set.operations or [],
        created_by=str(patch_set.created_by),
        created_at=patch_set.created_at,
    )


@router.post("/{patch_id}/generate", response_model=PatchSetResponse)
async def generate_patch_for_existing(
    patch_id: UUID,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(PatchSetModel).where(
            PatchSetModel.id == patch_id,
        )
    )
    patch = result.scalar_one_or_none()
    if patch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patch set not found")

    doc_result = await session.execute(
        select(DocumentModel).where(
            DocumentModel.id == patch.document_id,
        )
    )
    doc = doc_result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    doc_dict = {
        "id": str(doc.id),
        "title": doc.title or "",
        "version": doc.version,
        "content": doc.content or {},
    }

    provider = get_llm_provider()
    service = PatchService(llm=provider)
    plan = await service.generate_patch_plan(doc_dict, patch.summary, provider)

    raw_ops = plan.get("operations", [])
    patch.operations = _enrich_operations(raw_ops, patch_id)
    patch.summary = plan.get("summary", patch.summary)
    patch.version_from = doc.version
    patch.version_to = doc.version + 1
    try:
        await session.flush()
    except SQLAlchemyError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Database constraint violation",
        ) from exc

    logger.info(
        "Patch plan regenerated for patch set %s — %d operations",
        patch_id, len(patch.operations),
    )

    return PatchSetResponse(
        id=str(patch.id),
        document_id=str(patch.document_id),
        version_from=patch.version_from,
        version_to=patch.version_to,
        summary=patch.summary,
        operations=patch.operations or [],
        created_by=str(patch.created_by),
        created_at=patch.created_at,
    )


def _operation_text(content) -> str:
    """Best-effort plain-text preview of an operation's content."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content

    def _walk(node) -> str:
        if isinstance(node, dict):
            if node.get("type") == "text":
                return str(node.get("text", ""))
            return "".join(_walk(c) for c in node.get("content", []) or [])
        if isinstance(node, list):
            return "".join(_walk(c) for c in node)
        return ""

    if isinstance(content, dict):
        return _walk(content.get("content", content))
    return ""


@router.get("/document/{document_id}")
async def list_document_suggestions(
    document_id: UUID,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Flatten proposed patch-set operations for a document into review suggestions."""
    result = await session.execute(
        select(PatchSetModel).where(
            PatchSetModel.document_id == document_id,
            PatchSetModel.status == "proposed",
        ).order_by(PatchSetModel.created_at)
    )
    patch_sets = result.scalars().all()

    suggestions = []
    for ps in patch_sets:
        for op in ps.operations or []:
            op_type = op.get("operation", "replace")
            if op_type not in ("insert", "delete", "replace"):
                op_type = "replace"
            op_status = op.get("status", "pending")
            if op_status not in ("pending", "accepted", "rejected"):
                op_status = "pending"
            suggestions.append({
                "suggestionId": op.get("id", ""),
                "patchSetId": str(ps.id),
                "type": op_type,
                "status": op_status,
                "rationale": op.get("rationale"),
                "sectionId": op.get("target_section"),
                "insertedText": _operation_text(op.get("content")),
            })

    return {"data": {"suggestions": suggestions}}


@router.get("/{patch_id}", response_model=PatchSetResponse)
async def get_patch(
    patch_id: UUID,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(PatchSetModel).where(
            PatchSetModel.id == patch_id,
        )
    )
    patch = result.scalar_one_or_none()
    if patch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patch not found")

    return PatchSetResponse(
        id=str(patch.id),
        document_id=str(patch.document_id),
        version_from=patch.version_from,
        version_to=patch.version_to,
        summary=patch.summary,
        operations=patch.operations or [],
        created_by=str(patch.created_by),
        created_at=patch.created_at,
    )


def _find_operation(operations: list[dict], op_id: str) -> dict | None:
    for op in operations:
        if op.get("id") == op_id:
            return op
    return None


@router.post("/{patch_id}/operations/{op_id}/accept", response_model=dict)
async def accept_operation(
    patch_id: UUID,
    op_id: str,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(PatchSetModel).where(
            PatchSetModel.id == patch_id,
        )
    )
    patch = result.scalar_one_or_none()
    if patch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patch set not found")

    operation = _find_operation(patch.operations or [], op_id)
    if operation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operation not found")

    operation["status"] = "accepted"
    flag_modified(patch, "operations")
    try:
        await session.flush()
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Failed to accept operation",
        )
    return {"status": "accepted", "operation_id": op_id}


@router.post("/{patch_id}/operations/{op_id}/reject", response_model=dict)
async def reject_operation(
    patch_id: UUID,
    op_id: str,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(PatchSetModel).where(
            PatchSetModel.id == patch_id,
        )
    )
    patch = result.scalar_one_or_none()
    if patch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patch set not found")

    operation = _find_operation(patch.operations or [], op_id)
    if operation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operation not found")

    operation["status"] = "rejected"
    flag_modified(patch, "operations")
    try:
        await session.flush()
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Failed to reject operation",
        )
    return {"status": "rejected", "operation_id": op_id}


@router.post("/{patch_id}/apply", response_model=dict)
async def apply_patch(
    patch_id: UUID,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(PatchSetModel).where(
            PatchSetModel.id == patch_id,
        )
    )
    patch = result.scalar_one_or_none()
    if patch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patch set not found")

    doc_result = await session.execute(
        select(DocumentModel).where(
            DocumentModel.id == patch.document_id,
        )
    )
    doc = doc_result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    patch_set_dict = {
        "version_to": (patch.version_to or patch.version_from + 1),
        "operations": patch.operations or [],
    }
    doc_dict = {
        "version": doc.version,
        "content": doc.content or {},
    }

    service = PatchService()
    updated = await service.apply_patch(patch_set_dict, doc_dict)

    doc.content = updated.get("content", doc.content)
    doc.version += 1
    patch.version_to = doc.version
    patch.status = "applied"
    try:
        await session.flush()
    except SQLAlchemyError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Database constraint violation",
        ) from exc
    logger.info(
        "Patch set %s applied to document %s by user %s",
        patch_id, doc.id, current_user.user_id,
    )
    return {"status": "applied", "patch_id": patch_id, "new_version": doc.version}
