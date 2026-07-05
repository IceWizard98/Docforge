import asyncio
import json
import logging
import uuid

import asyncpg

from adapters.minio.storage import MinioStorageAdapter
from config.settings import get_settings
from core.events import ExportCompleted
from core.services.export import ExportService
from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _update_export_status(export_id: str, status: str, file_key: str = "") -> None:
    async def _run() -> None:
        settings = get_settings()
        dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
        # Connect, execute and close on ONE event loop — an asyncpg connection is
        # bound to the loop that created it, so separate asyncio.run() calls break.
        conn = await asyncpg.connect(dsn=dsn)
        try:
            payload = json.dumps({"status": status, "file_key": file_key})
            # MERGE into the payload (jsonb `||`) instead of overwriting it, so the
            # `format` key written at create time survives — the status/download
            # endpoints rely on it to build the right file_key. The column is
            # `json` (no `||` operator): cast to jsonb before merging.
            await conn.execute(
                "UPDATE audit_events SET payload = payload::jsonb || $1::jsonb WHERE id = $2",
                payload, uuid.UUID(export_id),
            )
        finally:
            await conn.close()

    try:
        asyncio.run(_run())
    except Exception:
        logger.exception("Failed to update export status for %s", export_id)


@celery_app.task
def export_document_task(
    export_id: str,
    document_id: str,
    document: dict,
    fmt: str,
    template_file_key: str | None = None,
) -> ExportCompleted:
    try:
        storage = MinioStorageAdapter()
        # Templates only apply to the DOCX-backed formats; markdown ignores them.
        template_bytes: bytes | None = None
        if template_file_key and fmt in {"pdf", "docx"}:
            template_bytes = asyncio.run(storage.download(template_file_key))

        service = ExportService()
        if fmt == "pdf":
            file_data = asyncio.run(service.export_pdf(document, template_bytes=template_bytes))
            content_type = "application/pdf"
        elif fmt == "docx":
            file_data = asyncio.run(service.export_docx(document, template_bytes=template_bytes))
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif fmt in {"md", "markdown"}:
            from adapters.export.markdown import export_markdown
            file_data = export_markdown(document.get("content", {})).encode("utf-8")
            content_type = "text/markdown"
        else:
            raise ValueError(f"Unsupported export format: {fmt}")

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
