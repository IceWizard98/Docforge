from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


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
                    "document_id": chunk.get("document_id", ""),
                    "source_document_id": chunk.get("source_document_id", ""),
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

    async def search_similar(
        self, query_embedding: list[float], limit: int = 10, tenant_id: str = ""
    ) -> list[dict]:
        embedding_literal = "[" + ",".join(str(v) for v in query_embedding) + "]"
        if tenant_id:
            result = await self.session.execute(
                text(
                    """
                    SELECT dc.id, dc.document_id, dc.section_id, dc.chunk_index,
                        dc.text_content, dc.metadata,
                        1 - (dc.embedding <=> :embedding::vector) AS similarity
                    FROM document_chunks dc
                    JOIN documents d ON d.id = dc.document_id AND d.tenant_id = :tenant_id
                    WHERE dc.embedding IS NOT NULL
                    ORDER BY dc.embedding <=> :embedding2::vector
                    LIMIT :limit
                    """
                ),
                {
                    "embedding": embedding_literal,
                    "embedding2": embedding_literal,
                    "tenant_id": tenant_id,
                    "limit": limit,
                },
            )
        else:
            result = await self.session.execute(
                text(
                    """
                    SELECT id, document_id, section_id, chunk_index,
                        text_content, metadata,
                        1 - (embedding <=> :embedding::vector) AS similarity
                    FROM document_chunks
                    WHERE embedding IS NOT NULL
                    ORDER BY embedding <=> :embedding2::vector
                    LIMIT :limit
                    """
                ),
                {
                    "embedding": embedding_literal,
                    "embedding2": embedding_literal,
                    "limit": limit,
                },
            )
        rows = result.all()
        return [dict(row._mapping) for row in rows]

    async def delete_document_embeddings(self, document_id: str) -> None:
        await self.session.execute(
            text("UPDATE document_chunks SET embedding = NULL WHERE document_id = :document_id"),
            {"document_id": document_id},
        )
        await self.session.flush()
