"""Create persistent API users.

Revision ID: identity_0002
Revises: identity_0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "identity_0002"
down_revision: str | None = "identity_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("username", sa.String(length=100), primary_key=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('EDITOR', 'ADMIN')", name="ck_users_role"),
        schema="identity_schema",
    )


def downgrade() -> None:
    op.drop_table("users", schema="identity_schema")
