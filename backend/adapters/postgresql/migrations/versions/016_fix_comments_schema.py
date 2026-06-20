"""016_fix_comments_schema

Revision ID: 016
Revises: 015
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "016"
down_revision = "015"


def upgrade():
    # 1. Add missing tenant_id column
    op.add_column(
        "comments",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # 2. Backfill tenant_id from parent document
    op.execute("""
        UPDATE comments c
        SET tenant_id = d.tenant_id
        FROM documents d
        WHERE c.document_id = d.id
          AND c.tenant_id IS NULL
    """)

    # 3. Make tenant_id NOT NULL and add index
    op.alter_column("comments", "tenant_id", nullable=False)
    op.create_index("idx_comments_tenant", "comments", ["tenant_id"])

    # 4. Add author column (String) alongside existing author_id (UUID)
    op.add_column(
        "comments",
        sa.Column("author", sa.String(255), nullable=True),
    )

    # 5. Backfill author from users table where possible,
    #    otherwise use author_id as string
    op.execute("""
        UPDATE comments c
        SET author = COALESCE(u.display_name, u.email, c.author_id::text)
        FROM users u
        WHERE c.author_id = u.id
    """)
    op.execute("""
        UPDATE comments SET author = author_id::text WHERE author IS NULL
    """)

    # 6. Make author NOT NULL and drop old author_id column
    op.alter_column("comments", "author", nullable=False)
    op.drop_column("comments", "author_id")

    # 7. Rename text -> content
    op.alter_column("comments", "text", new_column_name="content")


def downgrade():
    op.alter_column("comments", "content", new_column_name="text")
    op.add_column(
        "comments",
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute("UPDATE comments SET author_id = NULL WHERE author IS NOT NULL")
    op.drop_column("comments", "author")
    op.drop_index("idx_comments_tenant", table_name="comments")
    op.drop_column("comments", "tenant_id")
