import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
            DocumentModel.id == uuid.UUID(body.document_id),
            DocumentModel.tenant_id == uuid.UUID(current_user.tenant_id),
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
        tenant_id=uuid.UUID(current_user.tenant_id),
        document_id=uuid.UUID(body.document_id),
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
    await session.flush()

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
    patch_id: str,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(PatchSetModel).where(
            PatchSetModel.id == uuid.UUID(patch_id),
            PatchSetModel.tenant_id == uuid.UUID(current_user.tenant_id),
        )
    )
    patch = result.scalar_one_or_none()
    if patch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patch set not found")

    doc_result = await session.execute(
        select(DocumentModel).where(
            DocumentModel.id == patch.document_id,
            DocumentModel.tenant_id == uuid.UUID(current_user.tenant_id),
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
    await session.flush()

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


@router.get("/{patch_id}", response_model=PatchSetResponse)
async def get_patch(
    patch_id: str,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(PatchSetModel).where(
            PatchSetModel.id == uuid.UUID(patch_id),
            PatchSetModel.tenant_id == uuid.UUID(current_user.tenant_id),
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


@router.post("/{patch_id}/operations/{op_id}/accept", response_model=dict)
async def accept_operation(
    patch_id: str,
    op_id: str,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Accept operation requires real DB transaction — not yet implemented",
    )


@router.post("/{patch_id}/operations/{op_id}/reject", response_model=dict)
async def reject_operation(
    patch_id: str,
    op_id: str,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Reject operation requires real DB transaction — not yet implemented",
    )


@router.post("/{patch_id}/apply", response_model=dict)
async def apply_patch(
    patch_id: str,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(PatchSetModel).where(
            PatchSetModel.id == uuid.UUID(patch_id),
            PatchSetModel.tenant_id == uuid.UUID(current_user.tenant_id),
        )
    )
    patch = result.scalar_one_or_none()
    if patch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patch set not found")

    doc_result = await session.execute(
        select(DocumentModel).where(
            DocumentModel.id == patch.document_id,
            DocumentModel.tenant_id == uuid.UUID(current_user.tenant_id),
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
    await session.flush()
    logger.info(
        "Patch set %s applied to document %s by user %s",
        patch_id, doc.id, current_user.user_id,
    )
    return {"status": "applied", "patch_id": patch_id, "new_version": doc.version}
