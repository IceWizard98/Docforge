from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.postgresql.base import get_session
from adapters.postgresql.models import AuditEventModel, DocumentModel, TemplateModel
from api.middleware.auth import AuthUser, get_current_user
from api.schemas.exports import ExportCreate, ExportResponse
from workers.export import export_document_task

router = APIRouter(prefix="/exports", tags=["exports"])


@router.post(
    "/documents/{doc_id}/export",
    response_model=ExportResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_export(
    doc_id: UUID,
    body: ExportCreate,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    # Scope the lookup to the requesting user: a document the caller does not
    # own must be indistinguishable from one that does not exist, otherwise any
    # authenticated user could export (and download) another user's document.
    result = await session.execute(
        select(DocumentModel).where(
            DocumentModel.id == doc_id,
            DocumentModel.created_by == UUID(current_user.user_id),
        )
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Optional template: must be visible to the caller (public or own) and carry a
    # real DOCX file. Its MinIO key travels to the worker as a plain string.
    template_file_key: str | None = None
    if body.template_id is not None:
        owner = UUID(current_user.user_id)
        tpl_result = await session.execute(
            select(TemplateModel).where(
                TemplateModel.id == body.template_id,
                or_(TemplateModel.is_public.is_(True), TemplateModel.created_by == owner),
            )
        )
        template = tpl_result.scalar_one_or_none()
        if template is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
            )
        if not template.file_key:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="il template non ha un file DOCX",
            )
        template_file_key = template.file_key

    export_id = uuid4()
    payload: dict = {"format": body.format, "status": "processing"}
    if body.template_id is not None:
        payload["template_id"] = str(body.template_id)
    audit = AuditEventModel(
        id=export_id,
        user_id=UUID(current_user.user_id),
        event_type="export_created",
        entity_type="document",
        entity_id=str(doc_id),
        payload=payload,
    )
    session.add(audit)
    try:
        await session.flush()
    except SQLAlchemyError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Export already exists",
        )

    doc_data = {
        "id": str(doc_id),
        "title": doc.title,
        "content": doc.content,
        "version": doc.version,
    }
    # countdown gives the request transaction time to commit before the worker runs,
    # so the task doesn't race ahead of the audit/export row it expects.
    export_document_task.apply_async(
        (str(export_id), str(doc_id), doc_data, body.format, template_file_key), countdown=1
    )

    return ExportResponse(
        id=str(export_id),
        document_id=str(doc_id),
        format=body.format,
        status="processing",
        file_key=None,
        created_at=audit.created_at,
        updated_at=audit.created_at,
    )


@router.get("/{export_id}", response_model=ExportResponse)
async def get_export(
    export_id: UUID,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(AuditEventModel).where(
            AuditEventModel.id == export_id,
            AuditEventModel.event_type == "export_created",
            AuditEventModel.user_id == UUID(current_user.user_id),
        )
    )
    audit = result.scalar_one_or_none()
    if audit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")

    payload = audit.payload or {}
    fmt = payload.get("format", "pdf")
    job_status = payload.get("status", "processing")
    file_key = payload.get("file_key", "")
    if not file_key and job_status == "completed":
        file_key = f"exports/{audit.entity_id}/export.{fmt}"

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
    export_id: UUID,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(AuditEventModel).where(
            AuditEventModel.id == export_id,
            AuditEventModel.event_type == "export_created",
            AuditEventModel.user_id == UUID(current_user.user_id),
        )
    )
    audit = result.scalar_one_or_none()
    if audit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")

    payload = audit.payload or {}
    fmt = payload.get("format", "pdf")
    # Use the key the worker actually stored; fall back to the worker's naming scheme.
    file_key = payload.get("file_key") or f"exports/{audit.entity_id}/export.{fmt}"
    from adapters.minio.storage import MinioStorageAdapter

    storage = MinioStorageAdapter()
    try:
        data = await storage.download(file_key)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    media_types = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "md": "text/markdown",
        "markdown": "text/markdown",
    }
    return Response(
        content=data,
        media_type=media_types.get(fmt, "application/octet-stream"),
        headers={"Content-Disposition": f'attachment; filename="export.{fmt}"'},
    )
