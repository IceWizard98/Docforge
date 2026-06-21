"""014_add_chat_message_columns

Revision ID: 013
Revises: 012
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "014"
down_revision = "013"


def upgrade():
    op.add_column(
        "chat_messages",
        sa.Column(
            "source_refs", postgresql.JSON(),
            nullable=False, server_default=sa.text("'[]'::json"),
        ),
    )
    op.add_column(
        "chat_messages",
        sa.Column("action_type", sa.String(32), nullable=True),
    )


def downgrade():
    op.drop_column("chat_messages", "action_type")
    op.drop_column("chat_messages", "source_refs")
