"""017_fix_schema_mismatches

Revision ID: 017
Revises: 016
"""
import sqlalchemy as sa

from alembic import op

revision = "017"
down_revision = "016"


def upgrade():
    # M5: TemplateModel - created_at/updated_at should be NOT NULL
    op.alter_column("templates", "created_at", nullable=False,
                    server_default=sa.func.now(),
                    existing_type=sa.DateTime(timezone=True))
    op.alter_column("templates", "updated_at", nullable=False,
                    server_default=sa.func.now(),
                    existing_type=sa.DateTime(timezone=True))

    # M6: CitationModel - chunk_id should have FK to document_chunks.id
    op.create_foreign_key(
        "fk_citations_chunk_id",
        "citations", "document_chunks",
        ["chunk_id"], ["id"],
    )
    op.alter_column("citations", "created_at", nullable=False,
                    server_default=sa.func.now(),
                    existing_type=sa.DateTime(timezone=True))

    # M7: ProvenanceLinkModel - created_at NOT NULL
    op.alter_column("provenance_links", "created_at", nullable=False,
                    server_default=sa.func.now(),
                    existing_type=sa.DateTime(timezone=True))


def downgrade():
    op.alter_column("provenance_links", "created_at", nullable=True,
                    existing_type=sa.DateTime(timezone=True))
    op.alter_column("citations", "created_at", nullable=True,
                    existing_type=sa.DateTime(timezone=True))
    op.drop_constraint("fk_citations_chunk_id", "citations", type_="foreignkey")
    op.alter_column("templates", "updated_at", nullable=True,
                    existing_type=sa.DateTime(timezone=True))
    op.alter_column("templates", "created_at", nullable=True,
                    existing_type=sa.DateTime(timezone=True))
