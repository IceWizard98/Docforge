"""024_document_source_exclusions

Per-document source exclusion. A user can hide specific corpus sources from a
given document's RAG retrieval without deleting them from the corpus. Composite
PK (document_id, source_document_id) makes exclusions idempotent; both FKs
cascade on delete so removing a document or a source cleans up its exclusions.

Revision ID: 024
Revises: 023
"""
from alembic import op

revision = "024"
down_revision = "023"


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS document_source_exclusions (
            document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            source_document_id UUID NOT NULL
                REFERENCES source_documents(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (document_id, source_document_id)
        )
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS document_source_exclusions")
