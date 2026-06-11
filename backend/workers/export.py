from core.events import ExportCompleted


async def export_document_task(
    document_id: str, document: dict, fmt: str
) -> ExportCompleted:
    file_key = f"exports/{document_id}/export.{fmt}"
    return ExportCompleted(
        job_id=f"job_{document_id[:8]}",
        document_id=document_id,
        format=fmt,
        file_key=file_key,
    )
