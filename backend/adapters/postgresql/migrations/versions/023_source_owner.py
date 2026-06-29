"""023_source_owner

Add an owner (created_by) to source_documents so RAG retrieval and the source
endpoints can be scoped per user. Before this, sources/chunks were a global
corpus: any user's chat could retrieve and cite another user's uploaded
documents. Legacy rows keep created_by = NULL and are therefore excluded from
every user's owner-scoped retrieval.

Revision ID: 023
Revises: 022
"""
from alembic import op

revision = "023"
down_revision = "022"


def upgrade():
    op.execute(
        "ALTER TABLE source_documents ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES users(id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_sources_created_by ON source_documents(created_by)"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_sources_created_by")
    op.execute("ALTER TABLE source_documents DROP COLUMN IF EXISTS created_by")
