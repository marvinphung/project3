"""Create immutable publication snapshots.

Revision ID: content_0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "content_0002"
down_revision: str | None = "content_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA_NAME = "content_schema"


def upgrade() -> None:
    op.create_table(
        "publications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("generated_article_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("story_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("story_version", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=200), nullable=False),
        sa.Column("title_en", sa.Text(), nullable=False),
        sa.Column("body_en", sa.Text(), nullable=False),
        sa.Column("title_vi", sa.Text(), nullable=False),
        sa.Column("body_vi", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("story_version >= 1", name="ck_publication_story_version"),
        sa.CheckConstraint("length(trim(slug)) > 0", name="ck_publication_slug"),
        sa.PrimaryKeyConstraint("id", name="pk_publications"),
        sa.UniqueConstraint("revision_id", name="uq_publications_revision"),
        sa.UniqueConstraint("idempotency_key", name="uq_publications_idempotency_key"),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_publications_slug", "publications", ["slug"], unique=True, schema=SCHEMA_NAME
    )


def downgrade() -> None:
    op.drop_index("ix_publications_slug", table_name="publications", schema=SCHEMA_NAME)
    op.drop_table("publications", schema=SCHEMA_NAME)
