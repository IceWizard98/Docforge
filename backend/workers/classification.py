import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from adapters.llm.factory import get_llm_provider
from adapters.postgresql.models import DocumentModel, SourceDocumentModel
from config.settings import get_settings
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
- "jurisdiction": the jurisdiction if applicable (e.g. "US", "EU", "UK", "IT", or "")
- "parties": an array of party names mentioned in the document, or empty array

Respond with valid JSON only."""


def _extract_text_from_prosemirror(content: dict | None) -> str:
    if not content or not isinstance(content, dict):
        return ""
    parts = []
    for node in content.get("content") or []:
        if node.get("type") == "paragraph":
            for inline in node.get("content") or []:
                if inline.get("type") == "text":
                    parts.append(inline.get("text", ""))
            parts.append("\n")
        elif node.get("type") == "heading":
            for inline in node.get("content") or []:
                if inline.get("type") == "text":
                    parts.append(inline.get("text", ""))
            parts.append("\n\n")
    return "".join(parts)


@celery_app.task
def classify_document_task(source_doc_id: str, doc_id: str) -> DocumentClassified:
    try:
        settings = get_settings()
        engine = create_async_engine(settings.database_url, echo=False)
        session_factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        async def _run():
            from uuid import UUID

            async with session_factory() as session:
                src_result = await session.execute(
                    select(SourceDocumentModel).where(
                        SourceDocumentModel.id == UUID(source_doc_id)
                    )
                )
                source_doc = src_result.scalar_one_or_none()
                if source_doc is None:
                    logger.error("Source document %s not found", source_doc_id)
                    return DocumentClassified(document_id=doc_id)

                content = _extract_text_from_prosemirror(source_doc.parsed_content)
                if not content:
                    content = source_doc.parsed_text or ""

                provider = get_llm_provider()
                prompt = CLASSIFY_PROMPT_TEMPLATE.format(
                    content=content[:4000] if content else "(empty)"
                )
                result_data = await provider.generate_structured(prompt, dict)

                doc_type = result_data.get("doc_type", "unknown")
                language = result_data.get("language", "unknown")
                tags = result_data.get("tags", [])
                jurisdiction = result_data.get("jurisdiction", "")
                parties = result_data.get("parties", [])

                source_doc.doc_type = doc_type
                source_doc.language = language
                source_doc.jurisdiction = jurisdiction
                source_doc.tags = tags
                source_doc.parties = parties
                source_doc.classification_confidence = 0.8

                doc_result = await session.execute(
                    select(DocumentModel).where(DocumentModel.id == UUID(doc_id))
                )
                doc = doc_result.scalar_one_or_none()
                if doc:
                    doc.doc_type = doc_type
                    doc.language = language
                    doc.tags = tags

                await session.commit()

                return DocumentClassified(
                    document_id=doc_id,
                    doc_type=doc_type,
                    language=language,
                    tags=tags,
                    jurisdiction=jurisdiction,
                    parties=parties,
                    classification_confidence=0.8,
                )

        return asyncio.run(_run())
    except Exception as e:
        logger.error("Classification failed for doc %s: %s", doc_id, e)
        return DocumentClassified(document_id=doc_id)
