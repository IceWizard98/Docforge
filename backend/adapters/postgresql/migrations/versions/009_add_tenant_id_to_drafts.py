"""009_add_tenant_id_to_drafts

Revision ID: 009
Revises: 008
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "009"
down_revision = "008"


def upgrade():
    op.add_column(
        "drafts",
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
            index=True,
        ),
    )


def downgrade():
    op.drop_column("drafts", "tenant_id")
