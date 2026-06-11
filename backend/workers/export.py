import asyncio
import json
import logging

import asyncpg

from adapters.minio.storage import MinioStorageAdapter
from config.settings import get_settings
from core.events import ExportCompleted
from core.services.export import ExportService
from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _update_export_status(export_id: str, status: str, file_key: str = "") -> None:
    try:
        settings = get_settings()
        dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
        conn = asyncio.run(asyncpg.connect(dsn=dsn))
        try:
            payload = json.dumps({"status": status, "file_key": file_key})
            asyncio.run(
                conn.execute(
                    "UPDATE audit_events SET payload = $1 WHERE id = $2",
                    payload, export_id,
                )
            )
        finally:
            asyncio.run(conn.close())
    except Exception:
        logger.exception("Failed to update export status for %s", export_id)


@celery_app.task
def export_document_task(
    export_id: str, document_id: str, document: dict, fmt: str
) -> ExportCompleted:
    try:
        service = ExportService()
        if fmt == "pdf":
            file_data = asyncio.run(service.export_pdf(document))
            content_type = "application/pdf"
        elif fmt == "docx":
            file_data = asyncio.run(service.export_docx(document))
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        else:
            raise ValueError(f"Unsupported export format: {fmt}")

        storage = MinioStorageAdapter()
        file_key = f"exports/{document_id}/export.{fmt}"
        asyncio.run(storage.upload(file_key, file_data, content_type))

        _update_export_status(export_id, "completed", file_key)

        return ExportCompleted(
            job_id=export_id,
            document_id=document_id,
            format=fmt,
            file_key=file_key,
        )
    except Exception as e:
        logger.error("Export failed for %s (%s): %s", document_id, fmt, e)
        _update_export_status(export_id, "failed")
        return ExportCompleted(
            job_id=export_id,
            document_id=document_id,
            format=fmt,
            file_key="",
        )
