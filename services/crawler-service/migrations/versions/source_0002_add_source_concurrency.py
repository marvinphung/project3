"""Add source optimistic version and crawl batch idempotency.

Revision ID: source_0002
Revises: source_0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "source_0002"
down_revision: str | None = "source_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA_NAME = "source_schema"


def upgrade() -> None:
    op.add_column(
        "sources",
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        schema=SCHEMA_NAME,
    )
    op.create_check_constraint(
        "ck_sources_version",
        "sources",
        "version > 0",
        schema=SCHEMA_NAME,
    )
    op.add_column(
        "crawl_batches",
        sa.Column("idempotency_key", sa.String(length=256), nullable=True),
        schema=SCHEMA_NAME,
    )
    op.execute(
        sa.text(
            "UPDATE source_schema.crawl_batches "
            "SET idempotency_key = 'legacy:' || id::text "
            "WHERE idempotency_key IS NULL"
        )
    )
    op.alter_column(
        "crawl_batches",
        "idempotency_key",
        existing_type=sa.String(length=256),
        nullable=False,
        schema=SCHEMA_NAME,
    )
    op.create_unique_constraint(
        "uq_crawl_batches_idempotency_key",
        "crawl_batches",
        ["idempotency_key"],
        schema=SCHEMA_NAME,
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_crawl_batches_idempotency_key",
        "crawl_batches",
        schema=SCHEMA_NAME,
        type_="unique",
    )
    op.drop_column("crawl_batches", "idempotency_key", schema=SCHEMA_NAME)
    op.drop_constraint(
        "ck_sources_version",
        "sources",
        schema=SCHEMA_NAME,
        type_="check",
    )
    op.drop_column("sources", "version", schema=SCHEMA_NAME)
