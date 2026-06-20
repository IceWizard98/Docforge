"""012_citations_provenance

Revision ID: 012
Revises: 011
"""
import sqlalchemy as sa

from alembic import op

revision = "012"
down_revision = "011"


def upgrade():
    op.create_table(
        "citations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("chat_message_id", sa.UUID(), nullable=True),
        sa.Column("patch_set_id", sa.UUID(), nullable=True),
        sa.Column("chunk_id", sa.String(64), nullable=True),
        sa.Column("source_doc_id", sa.UUID(), nullable=True),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["chat_message_id"], ["chat_messages.id"]),
        sa.ForeignKeyConstraint(["patch_set_id"], ["patch_sets.id"]),
        sa.ForeignKeyConstraint(["source_doc_id"], ["source_documents.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_citations_chat_message_id", "citations", ["chat_message_id"])
    op.create_index("ix_citations_chunk_id", "citations", ["chunk_id"])

    op.create_table(
        "provenance_links",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("source_doc_id", sa.UUID(), nullable=False),
        sa.Column("section_id", sa.String(64), nullable=True),
        sa.Column("chunk_id", sa.String(64), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("version_number", sa.Integer(), nullable=True),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["source_doc_id"], ["source_documents.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_provenance_links_document_id", "provenance_links", ["document_id"])
    op.create_index("ix_provenance_links_chunk_id", "provenance_links", ["chunk_id"])

    op.add_column(
        "source_documents",
        sa.Column("language", sa.String(8), nullable=True),
    )
    op.add_column(
        "source_documents",
        sa.Column("jurisdiction", sa.String(64), nullable=True),
    )
    op.add_column(
        "source_documents",
        sa.Column("tags", sa.JSON(), nullable=True),
    )
    op.add_column(
        "source_documents",
        sa.Column("parties", sa.JSON(), nullable=True),
    )
    op.add_column(
        "source_documents",
        sa.Column("classification_confidence", sa.Float(), nullable=True),
    )
    op.add_column(
        "source_documents",
        sa.Column("parsed_text", sa.Text(), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("tags", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
    )


def downgrade():
    op.drop_column("documents", "tags")
    op.drop_column("source_documents", "parsed_text")
    op.drop_column("source_documents", "classification_confidence")
    op.drop_column("source_documents", "parties")
    op.drop_column("source_documents", "tags")
    op.drop_column("source_documents", "jurisdiction")
    op.drop_column("source_documents", "language")
    op.drop_index("ix_provenance_links_chunk_id", table_name="provenance_links")
    op.drop_index("ix_provenance_links_document_id", table_name="provenance_links")
    op.drop_table("provenance_links")
    op.drop_index("ix_citations_chunk_id", table_name="citations")
    op.drop_index("ix_citations_chat_message_id", table_name="citations")
    op.drop_table("citations")
