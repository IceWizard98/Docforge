"""002_documents

Revision ID: 002
Revises: 001

Adds the documents table for document storage.
RLS will be applied at the application layer via tenant_id scoping.
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "002"
down_revision = "001"


def upgrade():
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("doc_type", sa.String(64), nullable=False, server_default=""),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("language", sa.String(8), nullable=False, server_default="it"),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("content", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("outline", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("idx_documents_tenant", "documents", ["tenant_id"])
    op.create_index("idx_documents_status", "documents", ["status"])


def downgrade():
    op.drop_table("documents")
