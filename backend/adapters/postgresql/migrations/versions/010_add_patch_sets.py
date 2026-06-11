"""010_add_patch_sets

Revision ID: 010
Revises: 009
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "010"
down_revision = "009"


def upgrade():
    op.create_table(
        "patch_sets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"),
                  nullable=False, index=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id"),
                  nullable=False, index=True),
        sa.Column("chat_message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version_from", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("version_to", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="proposed"),
        sa.Column("summary", sa.String(500), nullable=False, server_default=""),
        sa.Column("operations", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade():
    op.drop_table("patch_sets")
