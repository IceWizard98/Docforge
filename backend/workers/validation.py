import asyncio
import logging

from core.events import DocumentValidated
from core.services.validation import ValidationService
from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task
def validate_document_task(
    document_id: str, document: dict, spec: dict | None = None
) -> DocumentValidated:
    try:
        service = ValidationService()
        result = asyncio.run(service.validate_document(document, spec))
        return DocumentValidated(
            document_id=document_id,
            version_number=document.get("version", 0),
            score=result.get("score", 0),
        )
    except Exception as e:
        logger.error("Document validation failed for %s: %s", document_id, e)
        return DocumentValidated(
            document_id=document_id,
            version_number=document.get("version", 0),
            score=0,
        )
