from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.services.search import RetrievalFilters


class PgvectorAdapter:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_extension(self) -> None:
        await self.session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await self.session.flush()

    async def store_embeddings(
        self, chunks: list[dict], embeddings: list[list[float]]
    ) -> None:
        for chunk, embedding in zip(chunks, embeddings, strict=False):
            embedding_literal = "[" + ",".join(str(v) for v in embedding) + "]"
            await self.session.execute(
                text(
                    """
                    INSERT INTO document_chunks (id, document_id, source_document_id,
                        section_id, chunk_index, text_content, token_count, metadata, embedding)
                    VALUES (:id, :document_id, :source_document_id,
                        :section_id, :chunk_index, :text_content,
                        :token_count, :metadata, :embedding::vector)
                    ON CONFLICT (id) DO UPDATE SET
                        embedding = :embedding2::vector,
                        text_content = :text_content,
                        token_count = :token_count
                    """
                ),
                {
                    "id": chunk.get("id", ""),
                    "document_id": chunk.get("document_id") or None,
                    "source_document_id": chunk.get("source_document_id") or None,
                    "section_id": chunk.get("section_id"),
                    "chunk_index": chunk.get("chunk_index", 0),
                    "text_content": chunk.get("text", ""),
                    "token_count": chunk.get("token_count", 0),
                    "metadata": chunk.get("metadata", {}),
                    "embedding": embedding_literal,
                    "embedding2": embedding_literal,
                },
            )
        await self.session.flush()

    def _build_filter_clauses(self, filters: RetrievalFilters | None) -> tuple[str, dict]:
        if not filters:
            return "", {}
        clauses: list[str] = []
        params: dict[str, Any] = {}

        if filters.doc_type:
            placeholders = ",".join(f":dt_{i}" for i in range(len(filters.doc_type)))
            clauses.append(f"sd.doc_type IN ({placeholders})")
            for i, t in enumerate(filters.doc_type):
                params[f"dt_{i}"] = t

        if filters.tags:
            tag_holders = ",".join(f":tg_{i}" for i in range(len(filters.tags)))
            clauses.append(f"sd.tags::jsonb ?| ARRAY[{tag_holders}]")
            for i, t in enumerate(filters.tags):
                params[f"tg_{i}"] = t

        if filters.language:
            clauses.append("sd.language = :language")
            params["language"] = filters.language

        if filters.chunk_type:
            clauses.append("dc.metadata->>'chunk_type' = :chunk_type")
            params["chunk_type"] = filters.chunk_type

        if filters.confidence_min is not None:
            clauses.append("sd.classification_confidence >= :confidence_min")
            params["confidence_min"] = filters.confidence_min

        if clauses:
            return " AND " + " AND ".join(clauses), params
        return "", {}

    async def search_similar(
        self,
        query_embedding: list[float],
        limit: int = 10,
        filters: RetrievalFilters | None = None,
    ) -> list[dict]:
        embedding_literal = "[" + ",".join(str(v) for v in query_embedding) + "]"
        filter_clause, filter_params = self._build_filter_clauses(filters)

        base_params: dict[str, Any] = {
            "embedding": embedding_literal,
            "embedding2": embedding_literal,
            "limit": limit,
        }
        base_params.update(filter_params)

        query = f"""
            SELECT dc.id as chunk_id, dc.document_id as doc_id, dc.section_id,
                dc.chunk_index, dc.text_content as content, dc.metadata,
                1 - (dc.embedding <=> :embedding::vector) AS score
            FROM document_chunks dc
            LEFT JOIN source_documents sd ON sd.id = dc.source_document_id
            WHERE dc.embedding IS NOT NULL{filter_clause}
            ORDER BY dc.embedding <=> :embedding2::vector
            LIMIT :limit
        """  # noqa: S608

        result = await self.session.execute(text(query), base_params)
        rows = result.all()
        return [dict(row._mapping) for row in rows]

    async def fulltext_search(
        self,
        query_text: str,
        limit: int = 10,
        filters: RetrievalFilters | None = None,
    ) -> list[dict]:
        filter_clause, filter_params = self._build_filter_clauses(filters)

        base_params: dict[str, Any] = {
            "query_text": query_text,
            "limit": limit,
        }
        base_params.update(filter_params)

        query = f"""
            SELECT dc.id as chunk_id, dc.document_id as doc_id, dc.section_id,
                dc.chunk_index, dc.text_content as content, dc.metadata,
                ts_rank(to_tsvector('italian', coalesce(dc.text_content, '')),
                        plainto_tsquery('italian', :query_text)) AS score
            FROM document_chunks dc
            LEFT JOIN source_documents sd ON sd.id = dc.source_document_id
            WHERE to_tsvector('italian', coalesce(dc.text_content, ''))
                  @@ plainto_tsquery('italian', :query_text){filter_clause}
            ORDER BY score DESC
            LIMIT :limit
        """  # noqa: S608

        result = await self.session.execute(text(query), base_params)
        rows = result.all()
        return [dict(row._mapping) for row in rows]

    async def delete_document_embeddings(self, document_id: str) -> None:
        await self.session.execute(
            text("UPDATE document_chunks SET embedding = NULL WHERE document_id = :document_id"),
            {"document_id": document_id},
        )
        await self.session.flush()

    async def has_fulltext_search(self) -> bool:
        result = await self.session.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'document_chunks' AND column_name = 'tsv_content'"
            )
        )
        return result.scalar() is not None
