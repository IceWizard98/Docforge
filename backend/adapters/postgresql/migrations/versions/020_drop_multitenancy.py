"""020_drop_multitenancy

Remove multi-tenancy: drop every tenant_id column, the tenants table, and the
tenant-scoped unique constraint on users (replaced by a global unique email).

Revision ID: 020
Revises: 019
"""
from alembic import op

revision = "020"
down_revision = "019"

_TENANT_TABLES = [
    "users",
    "documents",
    "source_documents",
    "document_chunks",
    "chat_sessions",
    "comments",
    "patch_sets",
    "templates",
    "audit_events",
    "drafts",
    "document_versions",
    "citations",
    "provenance_links",
]


def upgrade():
    # Users: swap tenant-scoped uniqueness for a global unique email.
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS uq_tenant_email")
    op.execute("DELETE FROM users a USING users b WHERE a.ctid < b.ctid AND a.email = b.email")

    # Drop tenant_id from every table (DROP COLUMN also removes its FK/index).
    for table in _TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS tenant_id")

    op.execute("ALTER TABLE users ADD CONSTRAINT uq_user_email UNIQUE (email)")
    op.execute("DROP TABLE IF EXISTS tenants CASCADE")


def downgrade():
    # Best-effort, lossy: recreate the structures without data.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS tenants (
            id UUID PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            slug VARCHAR(64) UNIQUE NOT NULL,
            config JSON NOT NULL DEFAULT '{}',
            status VARCHAR(32) NOT NULL DEFAULT 'active',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS uq_user_email")
    for table in _TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS tenant_id UUID")
