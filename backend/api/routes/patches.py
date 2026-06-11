import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.postgresql.base import get_session
from adapters.postgresql.models import DocumentModel, PatchSetModel
from api.middleware.auth import AuthUser, get_current_user
from api.schemas.patches import PatchGenerateRequest, PatchSetResponse
from core.services.patching import PatchService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/patches", tags=["patches"])


@router.post("", response_model=PatchSetResponse, status_code=status.HTTP_201_CREATED)
async def generate_patch(
    body: PatchGenerateRequest,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    import uuid

    result = await session.execute(
        select(DocumentModel).where(
            DocumentModel.id == uuid.UUID(body.document_id),
            DocumentModel.tenant_id == uuid.UUID(current_user.tenant_id),
        )
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    patch_set = PatchSetModel(
        id=uuid.uuid4(),
        tenant_id=uuid.UUID(current_user.tenant_id),
        document_id=uuid.UUID(body.document_id),
        version_from=doc.version,
        version_to=doc.version + 1,
        status="proposed",
        summary=f"Patch generated from: {body.instructions[:100]}",
        operations=[],
        created_by=uuid.UUID(current_user.user_id),
    )
    session.add(patch_set)
    await session.flush()

    return PatchSetResponse(
        id=str(patch_set.id),
        document_id=body.document_id,
        version_from=patch_set.version_from,
        version_to=patch_set.version_to,
        summary=patch_set.summary,
        operations=[],
        created_by=str(patch_set.created_by),
        created_at=patch_set.created_at,
    )


@router.get("/{patch_id}", response_model=PatchSetResponse)
async def get_patch(
    patch_id: str,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    import uuid

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


def _resolve_operation(
    patch: PatchSetModel, op_id: str, new_status: str
) -> dict | None:
    for op in (patch.operations or []):
        if op.get("id") == op_id or op.get("operation_id") == op_id:
            op["status"] = new_status
            return op
    return None


def _update_patch_set_status(patch: PatchSetModel) -> None:
    ops = patch.operations or []
    if not ops:
        return
    statuses = {op.get("status", "pending") for op in ops}
    if statuses == {"accepted"}:
        patch.status = "accepted"
    elif statuses == {"rejected"}:
        patch.status = "rejected"
    elif "pending" not in statuses:
        patch.status = "partially_resolved"


@router.post("/{patch_id}/operations/{op_id}/accept", response_model=dict)
async def accept_operation(
    patch_id: str,
    op_id: str,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    import uuid

    result = await session.execute(
        select(PatchSetModel).where(
            PatchSetModel.id == uuid.UUID(patch_id),
            PatchSetModel.tenant_id == uuid.UUID(current_user.tenant_id),
        )
    )
    patch = result.scalar_one_or_none()
    if patch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patch set not found")

    op = _resolve_operation(patch, op_id, "accepted")
    if op is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operation not found")

    _update_patch_set_status(patch)
    await session.flush()
    logger.info(
        "Operation %s accepted in patch set %s by user %s",
        op_id, patch_id, current_user.user_id,
    )
    return {"status": "accepted", "patch_id": patch_id, "operation_id": op_id}


@router.post("/{patch_id}/operations/{op_id}/reject", response_model=dict)
async def reject_operation(
    patch_id: str,
    op_id: str,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    import uuid

    result = await session.execute(
        select(PatchSetModel).where(
            PatchSetModel.id == uuid.UUID(patch_id),
            PatchSetModel.tenant_id == uuid.UUID(current_user.tenant_id),
        )
    )
    patch = result.scalar_one_or_none()
    if patch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patch set not found")

    op = _resolve_operation(patch, op_id, "rejected")
    if op is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operation not found")

    _update_patch_set_status(patch)
    await session.flush()
    logger.info(
        "Operation %s rejected in patch set %s by user %s",
        op_id, patch_id, current_user.user_id,
    )
    return {"status": "rejected", "patch_id": patch_id, "operation_id": op_id}


@router.post("/{patch_id}/apply", response_model=dict)
async def apply_patch(
    patch_id: str,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    import uuid

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
