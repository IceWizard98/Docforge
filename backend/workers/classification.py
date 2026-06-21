import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from adapters.llm.embeddings import create_embedding_provider
from adapters.llm.factory import get_llm_provider
from adapters.postgresql.models import DocumentModel, SourceDocumentModel
from adapters.postgresql.pgvector import PgvectorAdapter
from config.settings import get_settings
from core.doc_types import CANONICAL_DOC_TYPES, normalize
from core.events import DocumentClassified
from core.services.chunking import ChunkingService, _node_text
from workers.celery_app import celery_app

logger = logging.getLogger(__name__)

CLASSIFY_PROMPT_TEMPLATE = """Analyze the following document content and classify it.

Content:
{content}

Return a JSON object with:
- "doc_type": the document type, chosen STRICTLY from this list: {doc_types}.
  Use "other" if none fits.
- "language": the detected language code (e.g. "en", "it", "fr", "de", "es")
- "tags": an array of 2-5 relevant tag strings describing the document
- "jurisdiction": the jurisdiction if applicable (e.g. "US", "EU", "UK", "IT", or "")
- "parties": an array of party names mentioned in the document, or empty array

Respond with valid JSON only."""


def _extract_text_from_prosemirror(content: dict | None) -> str:
    """Full recursive plain-text extraction (lists, tables, clauses, nesting)."""
    if not content or not isinstance(content, dict):
        return ""
    return _node_text(content)


@celery_app.task
def classify_document_task(source_doc_id: str, doc_id: str | None = None) -> DocumentClassified:  # noqa: PLR0915
    try:
        settings = get_settings()
        engine = create_async_engine(settings.database_url, echo=False)
        session_factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        async def _run():  # noqa: PLR0915
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
                    content=content[:4000] if content else "(empty)",
                    doc_types=", ".join(CANONICAL_DOC_TYPES),
                )
                result_data = await provider.generate_structured(prompt, dict)

                doc_type = normalize(result_data.get("doc_type"))
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

                if doc_id:
                    doc_result = await session.execute(
                        select(DocumentModel).where(DocumentModel.id == UUID(doc_id))
                    )
                    doc = doc_result.scalar_one_or_none()
                    if doc:
                        doc.doc_type = doc_type
                        doc.language = language
                        doc.tags = tags

                source_doc.status = "indexing"
                await session.commit()

                try:
                    chunking = ChunkingService()
                    sid = str(source_doc.id)
                    did = str(doc_id) if doc_id else ""
                    # Prefer section-aware chunking from the ProseMirror structure;
                    # fall back to flat windowing for plain-text sources.
                    chunks = chunking.chunk_prosemirror(
                        source_doc.parsed_content, doc_id=did, source_id=sid, target_tokens=750
                    )
                    if not chunks:
                        text_to_chunk = source_doc.parsed_text or content or ""
                        if text_to_chunk:
                            chunks = chunking.chunk_text(text_to_chunk, target_tokens=750)
                    if chunks:
                        chunk_dicts = [
                            {
                                "id": c.id,
                                "document_id": did or None,
                                "source_document_id": sid,
                                "section_id": c.section_id,
                                "chunk_index": c.chunk_index,
                                "text": c.text,
                                "token_count": c.token_count,
                                "metadata": {
                                    **c.metadata,
                                    "source_document_id": sid,
                                    "document_id": did or None,
                                },
                            }
                            for c in chunks
                        ]
                        embedding_provider = create_embedding_provider(settings)
                        embeddings = await asyncio.gather(
                            *(embedding_provider.generate_embedding(c.text) for c in chunks)
                        )
                        pgvector = PgvectorAdapter(session)
                        await pgvector.store_embeddings(chunk_dicts, list(embeddings))
                        logger.info(
                            "Stored %d chunks with embeddings for source %s",
                            len(chunks), source_doc.id,
                        )
                    source_doc.status = "indexed"
                    await session.commit()
                except Exception as chunk_err:
                    logger.error(
                        "Chunking/embedding failed for source %s: %s",
                        source_doc.id, chunk_err,
                    )
                    source_doc.status = "failed"
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
