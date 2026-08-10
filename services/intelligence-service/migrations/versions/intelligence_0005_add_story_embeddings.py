"""Add immutable versioned Story embeddings.

Revision ID: intelligence_0005
Revises: intelligence_0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import VECTOR
from sqlalchemy.dialects import postgresql

revision: str = "intelligence_0005"
down_revision: str | None = "intelligence_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA_NAME = "intelligence_schema"


def upgrade() -> None:
    op.create_table(
        "story_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("story_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("story_version", sa.Integer(), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("input_builder_version", sa.String(length=100), nullable=False),
        sa.Column("model_name", sa.String(length=200), nullable=False),
        sa.Column("model_version", sa.String(length=200), nullable=False),
        sa.Column("dimensions", sa.SmallInteger(), nullable=False),
        sa.Column("embedding", VECTOR(384), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["story_id"],
            [f"{SCHEMA_NAME}.stories.id"],
            name="fk_story_embeddings_story",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("story_version >= 1", name="ck_story_embeddings_version"),
        sa.CheckConstraint(
            "input_hash ~ '^[0-9a-f]{64}$'",
            name="ck_story_embeddings_input_hash",
        ),
        sa.CheckConstraint("dimensions = 384", name="ck_story_embeddings_dimensions"),
        sa.CheckConstraint("token_count > 0", name="ck_story_embeddings_token_count"),
        sa.PrimaryKeyConstraint("id", name="pk_story_embeddings"),
        sa.UniqueConstraint(
            "story_id",
            "story_version",
            "input_hash",
            "model_name",
            "model_version",
            name="uq_story_embeddings_input_model",
        ),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_story_embeddings_story_version",
        "story_embeddings",
        ["story_id", "story_version"],
        schema=SCHEMA_NAME,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_story_embeddings_story_version",
        table_name="story_embeddings",
        schema=SCHEMA_NAME,
    )
    op.drop_table("story_embeddings", schema=SCHEMA_NAME)
