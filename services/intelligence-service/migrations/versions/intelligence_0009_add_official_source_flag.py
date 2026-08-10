"""Mark authoritative Story sources for claim confirmation.

Revision ID: intelligence_0009
Revises: intelligence_0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "intelligence_0009"
down_revision: str | None = "intelligence_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA_NAME = "intelligence_schema"


def upgrade() -> None:
    op.add_column(
        "story_sources",
        sa.Column("is_official", sa.Boolean(), nullable=False, server_default=sa.false()),
        schema=SCHEMA_NAME,
    )
    op.alter_column("story_sources", "is_official", server_default=None, schema=SCHEMA_NAME)


def downgrade() -> None:
    op.drop_column("story_sources", "is_official", schema=SCHEMA_NAME)
