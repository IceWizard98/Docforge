import asyncio
import logging

from adapters.llm.factory import get_llm_provider
from core.events import DocumentClassified
from workers.celery_app import celery_app

logger = logging.getLogger(__name__)

CLASSIFY_PROMPT_TEMPLATE = """Analyze the following document content and classify it.

Content:
{content}

Return a JSON object with:
- "doc_type": the document type (e.g. "contract", "report", "memo", "letter", "proposal", "other")
- "language": the detected language code (e.g. "en", "it", "fr", "de", "es")
- "tags": an array of 2-5 relevant tag strings describing the document

Respond with valid JSON only."""


@celery_app.task
def classify_document_task(document_id: str, document_content: str) -> DocumentClassified:
    try:
        provider = get_llm_provider()
        prompt = CLASSIFY_PROMPT_TEMPLATE.format(
            content=document_content[:4000] if document_content else "(empty)"
        )
        result = asyncio.run(provider.generate_structured(prompt, dict))
        return DocumentClassified(
            document_id=document_id,
            doc_type=result.get("doc_type", "unknown"),
            language=result.get("language", "unknown"),
            tags=result.get("tags", []),
        )
    except Exception as e:
        logger.error("Classification failed for %s: %s", document_id, e)
        return DocumentClassified(document_id=document_id)



