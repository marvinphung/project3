"""Add unresolved entity mention review queue.

Revision ID: intelligence_0002
Revises: intelligence_0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "intelligence_0002"
down_revision: str | None = "intelligence_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA_NAME = "intelligence_schema"


def upgrade() -> None:
    op.create_table(
        "unresolved_entity_mentions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("article_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_field", sa.String(length=16), nullable=False),
        sa.Column("mention_text", sa.String(length=200), nullable=False),
        sa.Column("normalized_alias", sa.String(length=200), nullable=False),
        sa.Column("predicted_type", sa.String(length=32), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("model_name", sa.String(length=200), nullable=False),
        sa.Column("model_version", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="PENDING_REVIEW", nullable=False),
        sa.Column("resolved_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_by", sa.String(length=200), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "source_field IN ('TITLE', 'CONTENT')",
            name="ck_unresolved_source_field",
        ),
        sa.CheckConstraint(
            "predicted_type IN ('PLAYER', 'CLUB', 'COACH', 'COMPETITION')",
            name="ck_unresolved_predicted_type",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING_REVIEW', 'RESOLVED', 'REJECTED')",
            name="ck_unresolved_status",
        ),
        sa.CheckConstraint(
            "start_offset >= 0 AND end_offset > start_offset",
            name="ck_unresolved_offsets",
        ),
        sa.CheckConstraint("score >= 0 AND score <= 1", name="ck_unresolved_score"),
        sa.ForeignKeyConstraint(
            ["resolved_entity_id"],
            [f"{SCHEMA_NAME}.entities.id"],
            name="fk_unresolved_resolved_entity_id_entities",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_unresolved_entity_mentions"),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_unresolved_status_created",
        "unresolved_entity_mentions",
        ["status", "created_at"],
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_unresolved_article_version",
        "unresolved_entity_mentions",
        ["article_version_id"],
        schema=SCHEMA_NAME,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_unresolved_article_version",
        table_name="unresolved_entity_mentions",
        schema=SCHEMA_NAME,
    )
    op.drop_index(
        "ix_unresolved_status_created",
        table_name="unresolved_entity_mentions",
        schema=SCHEMA_NAME,
    )
    op.drop_table("unresolved_entity_mentions", schema=SCHEMA_NAME)
