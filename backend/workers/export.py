import asyncio
import logging

from adapters.minio.storage import MinioStorageAdapter
from core.events import ExportCompleted
from core.services.export import ExportService
from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task
def export_document_task(
    document_id: str, document: dict, fmt: str
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

        return ExportCompleted(
            job_id=f"job_{document_id[:8]}",
            document_id=document_id,
            format=fmt,
            file_key=file_key,
        )
    except Exception as e:
        logger.error("Export failed for %s (%s): %s", document_id, fmt, e)
        return ExportCompleted(
            job_id=f"job_{document_id[:8]}",
            document_id=document_id,
            format=fmt,
            file_key="",
        )
