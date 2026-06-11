from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.postgresql.base import get_session
from adapters.postgresql.models import DocumentModel
from api.middleware.auth import AuthUser, get_current_user
from api.schemas.exports import ExportCreate, ExportResponse
from workers.export import export_document_task

_EXPORT_STATUS: dict[str, str] = {}

router = APIRouter(prefix="/exports", tags=["exports"])


@router.post(
    "/documents/{doc_id}/export",
    response_model=ExportResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_export(
    doc_id: str,
    body: ExportCreate,
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

    export_id = uuid.uuid4()
    from adapters.postgresql.models import AuditEventModel

    audit = AuditEventModel(
        id=export_id,
        tenant_id=uuid.UUID(current_user.tenant_id),
        user_id=uuid.UUID(current_user.user_id),
        event_type="export_created",
        entity_type="document",
        entity_id=doc_id,
        payload={"format": body.format, "status": "processing"},
    )
    session.add(audit)
    await session.flush()

    _EXPORT_STATUS[str(export_id)] = "processing"

    doc_data = {"id": doc_id, "title": doc.title, "content": doc.content, "version": doc.version}
    export_document_task.delay(str(export_id), doc_id, doc_data, body.format)

    return ExportResponse(
        id=str(export_id),
        document_id=doc_id,
        format=body.format,
        status="processing",
        file_key=None,
        created_at=audit.created_at,
        updated_at=audit.created_at,
    )


@router.get("/{export_id}", response_model=ExportResponse)
async def get_export(
    export_id: str,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    import uuid

    from adapters.postgresql.models import AuditEventModel

    result = await session.execute(
        select(AuditEventModel).where(
            AuditEventModel.id == uuid.UUID(export_id),
            AuditEventModel.tenant_id == uuid.UUID(current_user.tenant_id),
            AuditEventModel.event_type == "export_created",
        )
    )
    audit = result.scalar_one_or_none()
    if audit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")

    payload = audit.payload or {}
    fmt = payload.get("format", "pdf")
    job_status = payload.get("status", _EXPORT_STATUS.get(export_id, "processing"))
    file_key = payload.get("file_key", "")
    if not file_key and job_status == "completed":
        file_key = f"exports/{audit.entity_id}/{export_id}.{fmt}"

    return ExportResponse(
        id=str(audit.id),
        document_id=audit.entity_id,
        format=fmt,
        status=job_status,
        file_key=file_key,
        created_at=audit.created_at,
        updated_at=audit.created_at,
    )


@router.get("/{export_id}/download")
async def download_export(
    export_id: str,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    import uuid

    from adapters.postgresql.models import AuditEventModel

    result = await session.execute(
        select(AuditEventModel).where(
            AuditEventModel.id == uuid.UUID(export_id),
            AuditEventModel.tenant_id == uuid.UUID(current_user.tenant_id),
        )
    )
    audit = result.scalar_one_or_none()
    if audit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")

    fmt = (audit.payload or {}).get("format", "pdf")
    file_key = f"exports/{audit.entity_id}/{export_id}.{fmt}"
    from adapters.minio.storage import MinioStorageAdapter

    storage = MinioStorageAdapter()
    try:
        data = await storage.download(file_key)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    media_types = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    return Response(
        content=data,
        media_type=media_types.get(fmt, "application/octet-stream"),
        headers={"Content-Disposition": f'attachment; filename="export.{fmt}"'},
    )
