"""025_templates_file_owner

Give templates an owner (created_by) and an optional stored DOCX (file_key).
Before this, templates were a shared library with no ownership signal, so
mutation had to be forbidden outright. With created_by, list/read/update/delete
can be scoped per user. Legacy rows keep created_by = NULL (public library only,
admin-managed).

Revision ID: 025
Revises: 024
"""
from alembic import op

revision = "025"
down_revision = "024"


def upgrade():
    op.execute("ALTER TABLE templates ADD COLUMN IF NOT EXISTS file_key VARCHAR(500)")
    op.execute(
        "ALTER TABLE templates ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES users(id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_templates_created_by ON templates(created_by)"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_templates_created_by")
    op.execute("ALTER TABLE templates DROP COLUMN IF EXISTS created_by")
    op.execute("ALTER TABLE templates DROP COLUMN IF EXISTS file_key")
