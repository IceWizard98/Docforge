"""021_chat_message_transparency

Adds transparency columns to chat_messages so the "what I understood" summary
and per-slot status survive reload (previously only returned on the live reply).

Revision ID: 021
Revises: 020
"""
import sqlalchemy as sa

from alembic import op

revision = "021"
down_revision = "020"


def upgrade():
    op.add_column("chat_messages", sa.Column("intent_summary", sa.Text(), nullable=True))
    op.add_column(
        "chat_messages",
        sa.Column(
            "slot_status",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )


def downgrade():
    op.drop_column("chat_messages", "slot_status")
    op.drop_column("chat_messages", "intent_summary")
