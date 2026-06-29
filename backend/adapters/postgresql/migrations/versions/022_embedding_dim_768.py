"""022_embedding_dim_768

Switch the chunk embedding vector from 1536 (OpenAI text-embedding-3-small) to
768 (Ollama nomic-embed-text) for fully-local RAG. A vector dimension change
cannot be cast in place, so the column is dropped and recreated; existing
embeddings (previously all-zero stubs) are discarded and must be rebuilt via
POST /api/v1/sources/reindex-all.

Revision ID: 022
Revises: 021
"""
from alembic import op

revision = "022"
down_revision = "021"


def upgrade():
    op.execute("DROP INDEX IF EXISTS idx_chunks_embedding")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE document_chunks ADD COLUMN embedding vector(768)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_chunks_embedding "
        "ON document_chunks USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_chunks_embedding")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE document_chunks ADD COLUMN embedding vector(1536)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_chunks_embedding "
        "ON document_chunks USING hnsw (embedding vector_cosine_ops)"
    )
