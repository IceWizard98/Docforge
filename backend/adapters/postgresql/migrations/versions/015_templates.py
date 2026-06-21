"""015_templates

Revision ID: 013
Revises: 012
"""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "015"
down_revision = "014"


def upgrade():
    op.create_table(
        "templates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("doc_type", sa.String(50), nullable=True),
        sa.Column("content", JSONB(), nullable=False),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("is_public", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_templates_tenant"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_templates_tenant_id", "templates", ["tenant_id"])


def downgrade():
    op.drop_index("ix_templates_tenant_id")
    op.drop_table("templates")
