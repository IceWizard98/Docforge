"""011_add_email_verified

Revision ID: 011
Revises: 010
"""
import sqlalchemy as sa

from alembic import op

revision = "011"
down_revision = "010"


def upgrade():
    op.add_column(
        "users",
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade():
    op.drop_column("users", "email_verified")
