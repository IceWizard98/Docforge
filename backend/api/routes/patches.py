from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.postgresql.base import get_session
from adapters.postgresql.models import DocumentModel, PatchSetModel
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

    result = await session.execute(
        select(PatchSetModel).where(
            PatchSetModel.id == uuid.UUID(patch_id),
            PatchSetModel.tenant_id == uuid.UUID(current_user.tenant_id),
        )
    )
    patch = result.scalar_one_or_none()
    if patch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patch not found")

    doc_result = await session.execute(
        select(DocumentModel).where(
            DocumentModel.id == patch.document_id,
            DocumentModel.tenant_id == uuid.UUID(current_user.tenant_id),
        )
    )
    doc = doc_result.scalar_one_or_none()
    if doc:
        doc.version += 1
        await session.flush()
        patch.version_to = doc.version
        patch.status = "applied"
        await session.flush()

    return {"status": "applied", "patch_id": patch_id, "new_version": doc.version if doc else 0}
