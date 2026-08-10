"""Create editorial revision persistence.

Revision ID: content_0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "content_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA_NAME = "content_schema"


def upgrade() -> None:
    op.create_table(
        "editorial_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("generated_article_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("story_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("story_version", sa.Integer(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("title_en", sa.Text(), nullable=False),
        sa.Column("body_en", sa.Text(), nullable=False),
        sa.Column("title_vi", sa.Text(), nullable=False),
        sa.Column("body_vi", sa.Text(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("story_version >= 1", name="ck_editorial_story_version"),
        sa.CheckConstraint("revision_number >= 1", name="ck_editorial_revision_number"),
        sa.CheckConstraint(
            "state IN ('DRAFT', 'NEEDS_REVIEW', 'APPROVED', 'REJECTED', 'STALE')",
            name="ck_editorial_state",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_editorial_revisions"),
        sa.UniqueConstraint(
            "generated_article_id", "revision_number", name="uq_editorial_article_revision"
        ),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_editorial_current_revision",
        "editorial_revisions",
        ["generated_article_id", "revision_number"],
        unique=False,
        schema=SCHEMA_NAME,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_editorial_current_revision", table_name="editorial_revisions", schema=SCHEMA_NAME
    )
    op.drop_table("editorial_revisions", schema=SCHEMA_NAME)
