from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.postgresql.base import get_session
from adapters.postgresql.models import DocumentModel
from api.middleware.auth import AuthUser, get_current_user
from api.schemas.patches import PatchGenerateRequest, PatchSetResponse

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

    patch_id = uuid.uuid4()
    patch_data = {
        "id": str(patch_id),
        "document_id": body.document_id,
        "version_from": doc.version,
        "version_to": doc.version + 1,
        "summary": f"Patch generated from: {body.instructions[:100]}",
        "operations": [],
        "status": "proposed",
        "created_by": current_user.user_id,
        "created_at": "2025-01-01T00:00:00Z",
    }

    from adapters.postgresql.models import AuditEventModel

    audit = AuditEventModel(
        id=uuid.uuid4(),
        tenant_id=uuid.UUID(current_user.tenant_id),
        user_id=uuid.UUID(current_user.user_id),
        event_type="patch_generated",
        entity_type="document",
        entity_id=body.document_id,
        payload={"instructions": body.instructions[:200]},
    )
    session.add(audit)
    await session.flush()
    return PatchSetResponse(**patch_data)


@router.get("/{patch_id}", response_model=PatchSetResponse)
async def get_patch(
    patch_id: str,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    import uuid

    from adapters.postgresql.models import AuditEventModel

    result = await session.execute(
        select(AuditEventModel).where(
            AuditEventModel.id == uuid.UUID(patch_id),
            AuditEventModel.tenant_id == uuid.UUID(current_user.tenant_id),
            AuditEventModel.event_type == "patch_generated",
        )
    )
    audit = result.scalar_one_or_none()
    if audit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patch not found")

    return PatchSetResponse(
        id=str(audit.id),
        document_id=audit.entity_id,
        version_from=0,
        version_to=1,
        summary="Patch set",
        operations=[],
        created_by=str(audit.user_id),
        created_at=audit.created_at,
    )


@router.post("/{patch_id}/operations/{op_id}/accept", response_model=dict)
async def accept_operation(
    patch_id: str,
    op_id: str,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return {"status": "accepted", "patch_id": patch_id, "operation_id": op_id}


@router.post("/{patch_id}/operations/{op_id}/reject", response_model=dict)
async def reject_operation(
    patch_id: str,
    op_id: str,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return {"status": "rejected", "patch_id": patch_id, "operation_id": op_id}


@router.post("/{patch_id}/apply", response_model=dict)
async def apply_patch(
    patch_id: str,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    import uuid

    from adapters.postgresql.models import AuditEventModel

    result = await session.execute(
        select(AuditEventModel).where(
            AuditEventModel.id == uuid.UUID(patch_id),
            AuditEventModel.tenant_id == uuid.UUID(current_user.tenant_id),
        )
    )
    audit = result.scalar_one_or_none()
    if audit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patch not found")

    doc_result = await session.execute(
        select(DocumentModel).where(
            DocumentModel.id == uuid.UUID(audit.entity_id),
            DocumentModel.tenant_id == uuid.UUID(current_user.tenant_id),
        )
    )
    doc = doc_result.scalar_one_or_none()
    if doc:
        doc.version += 1
        await session.flush()

    return {"status": "applied", "patch_id": patch_id, "new_version": doc.version if doc else 0}
