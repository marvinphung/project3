"""Add source cluster identity for independence checks.

Revision ID: intelligence_0008
Revises: intelligence_0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "intelligence_0008"
down_revision: str | None = "intelligence_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA_NAME = "intelligence_schema"


def upgrade() -> None:
    op.add_column(
        "story_sources",
        sa.Column("source_cluster_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_story_sources_cluster",
        "story_sources",
        ["story_id", "source_cluster_id"],
        schema=SCHEMA_NAME,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_story_sources_cluster",
        table_name="story_sources",
        schema=SCHEMA_NAME,
    )
    op.drop_column("story_sources", "source_cluster_id", schema=SCHEMA_NAME)
