"""Add bilingual Story timeline entries.

Revision ID: intelligence_0010
Revises: intelligence_0009
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "intelligence_0010"
down_revision: str | None = "intelligence_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA_NAME = "intelligence_schema"


def upgrade() -> None:
    op.create_table(
        "timeline_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("story_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("summary_en", sa.Text(), nullable=False),
        sa.Column("summary_vi", sa.Text(), nullable=False),
        sa.Column("confirmation", sa.String(length=16), nullable=False),
        sa.Column("used_claim_ids", postgresql.JSONB(), nullable=False),
        sa.Column("source_article_ids", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("window_end > window_start", name="ck_timeline_window"),
        sa.CheckConstraint("length(trim(summary_en)) > 0", name="ck_timeline_summary_en"),
        sa.CheckConstraint("length(trim(summary_vi)) > 0", name="ck_timeline_summary_vi"),
        sa.CheckConstraint(
            "confirmation IN ('RUMOUR', 'REPORTED', 'MULTI_SOURCE', 'OFFICIAL')",
            name="ck_timeline_confirmation",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(used_claim_ids) = 'array' AND jsonb_array_length(used_claim_ids) > 0",
            name="ck_timeline_claim_ids",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source_article_ids) = 'array' AND "
            "jsonb_array_length(source_article_ids) > 0",
            name="ck_timeline_source_ids",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_timeline_entries"),
        sa.UniqueConstraint("story_id", "window_start", name="uq_timeline_story_window"),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_timeline_entries_story_window",
        "timeline_entries",
        ["story_id", "window_start"],
        schema=SCHEMA_NAME,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_timeline_entries_story_window",
        table_name="timeline_entries",
        schema=SCHEMA_NAME,
    )
    op.drop_table("timeline_entries", schema=SCHEMA_NAME)
