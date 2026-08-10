"""Store deterministic claim confirmation level.

Revision ID: intelligence_0007
Revises: intelligence_0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "intelligence_0007"
down_revision: str | None = "intelligence_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA_NAME = "intelligence_schema"


def upgrade() -> None:
    op.add_column(
        "claims",
        sa.Column(
            "confirmation",
            sa.String(length=16),
            nullable=False,
            server_default="RUMOUR",
        ),
        schema=SCHEMA_NAME,
    )
    op.create_check_constraint(
        "ck_claims_confirmation",
        "claims",
        "confirmation IN ('RUMOUR', 'REPORTED', 'MULTI_SOURCE', 'OFFICIAL')",
        schema=SCHEMA_NAME,
    )
    op.alter_column(
        "claims",
        "confirmation",
        server_default=None,
        schema=SCHEMA_NAME,
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_claims_confirmation",
        "claims",
        type_="check",
        schema=SCHEMA_NAME,
    )
    op.drop_column("claims", "confirmation", schema=SCHEMA_NAME)
