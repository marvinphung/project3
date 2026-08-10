"""Create transactional publication outbox.

Revision ID: content_0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "content_0003"
down_revision: str | None = "content_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA_NAME = "content_schema"


def upgrade() -> None:
    op.create_table(
        "publication_outbox",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("publication_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("topic", sa.String(length=100), nullable=False),
        sa.Column("message_key", sa.String(length=200), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False, server_default="PENDING"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("state IN ('PENDING', 'PUBLISHED')", name="ck_publication_outbox_state"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_publication_outbox_attempt_count"),
        sa.PrimaryKeyConstraint("event_id", name="pk_publication_outbox"),
        sa.UniqueConstraint("publication_id", name="uq_publication_outbox_publication"),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_publication_outbox_pending",
        "publication_outbox",
        ["state", "occurred_at"],
        schema=SCHEMA_NAME,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_publication_outbox_pending", table_name="publication_outbox", schema=SCHEMA_NAME
    )
    op.drop_table("publication_outbox", schema=SCHEMA_NAME)
