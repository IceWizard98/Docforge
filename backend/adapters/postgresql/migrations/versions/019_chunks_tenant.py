"""019_chunks_tenant

Add tenant_id to document_chunks (denormalized for fast, robust tenant-scoped
retrieval) and make document_id nullable so source-library chunks need not be
tied to a composed document.

Revision ID: 019
Revises: 018
"""
from alembic import op

revision = "019"
down_revision = "018"


def upgrade():
    # Add tenant_id (nullable first for backfill).
    op.execute("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS tenant_id UUID")

    # Backfill from the owning document, falling back to the source document.
    op.execute(
        """
        UPDATE document_chunks dc
        SET tenant_id = d.tenant_id
        FROM documents d
        WHERE d.id = dc.document_id AND dc.tenant_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE document_chunks dc
        SET tenant_id = sd.tenant_id
        FROM source_documents sd
        WHERE sd.id = dc.source_document_id AND dc.tenant_id IS NULL
        """
    )

    # Drop orphan chunks that could not be attributed to a tenant (safety: such
    # rows would otherwise be unreachable and block the NOT NULL constraint).
    op.execute("DELETE FROM document_chunks WHERE tenant_id IS NULL")

    op.execute("ALTER TABLE document_chunks ALTER COLUMN tenant_id SET NOT NULL")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_chunks_tenant ON document_chunks (tenant_id)"
    )

    # Source-library chunks are not tied to a composed document.
    op.execute("ALTER TABLE document_chunks ALTER COLUMN document_id DROP NOT NULL")


def downgrade():
    op.execute("ALTER TABLE document_chunks ALTER COLUMN document_id SET NOT NULL")
    op.execute("DROP INDEX IF EXISTS idx_chunks_tenant")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS tenant_id")
