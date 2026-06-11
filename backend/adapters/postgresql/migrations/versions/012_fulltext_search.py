"""012_fulltext_search

Revision ID: 012
Revises: 011
"""
import sqlalchemy as sa

from alembic import op

revision = "012"
down_revision = "011"


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.add_column(
        "document_chunks",
        sa.Column("tsv_content", sa.TSVECTOR(), nullable=True),
    )

    op.create_index(
        "ix_document_chunks_tsv",
        "document_chunks",
        ["tsv_content"],
        postgresql_using="gin",
    )

    op.execute("""
        CREATE OR REPLACE FUNCTION document_chunks_tsv_trigger() RETURNS trigger AS $$
        begin
          new.tsv_content := to_tsvector('italian', coalesce(new.text_content, ''));
          return new;
        end;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_document_chunks_tsv
        BEFORE INSERT OR UPDATE OF text_content ON document_chunks
        FOR EACH ROW EXECUTE FUNCTION document_chunks_tsv_trigger();
    """)

    op.execute(
        "UPDATE document_chunks "
        "SET tsv_content = to_tsvector('italian', coalesce(text_content, ''));"
    )

    op.create_index(
        "ix_document_chunks_trgm",
        "document_chunks",
        ["text_content"],
        postgresql_using="gin",
        postgresql_ops={"text_content": "gin_trgm_ops"},
    )


def downgrade():
    op.drop_index("ix_document_chunks_trgm", table_name="document_chunks")
    op.execute("DROP TRIGGER IF EXISTS trg_document_chunks_tsv ON document_chunks")
    op.execute("DROP FUNCTION IF EXISTS document_chunks_tsv_trigger()")
    op.drop_index("ix_document_chunks_tsv", table_name="document_chunks")
    op.drop_column("document_chunks", "tsv_content")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
