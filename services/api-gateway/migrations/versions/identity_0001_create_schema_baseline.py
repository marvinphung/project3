"""Record the identity owner schema baseline.

Revision ID: identity_0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "identity_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text("CREATE SCHEMA IF NOT EXISTS identity_schema"))


def downgrade() -> None:
    """Keep the owner namespace because it contains Alembic's version table."""
