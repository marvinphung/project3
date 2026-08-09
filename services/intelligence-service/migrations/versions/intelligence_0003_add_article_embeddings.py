"""Add immutable English article embeddings.

Revision ID: intelligence_0003
Revises: intelligence_0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import VECTOR
from sqlalchemy.dialects import postgresql

revision: str = "intelligence_0003"
down_revision: str | None = "intelligence_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA_NAME = "intelligence_schema"


def upgrade() -> None:
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
    op.create_table(
        "article_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("article_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("input_builder_version", sa.String(length=100), nullable=False),
        sa.Column("model_name", sa.String(length=200), nullable=False),
        sa.Column("model_version", sa.String(length=200), nullable=False),
        sa.Column("dimensions", sa.SmallInteger(), nullable=False),
        sa.Column("embedding", VECTOR(384), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("embedded_token_count", sa.Integer(), nullable=False),
        sa.Column("truncated", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("input_hash ~ '^[0-9a-f]{64}$'", name="ck_embeddings_input_hash"),
        sa.CheckConstraint("dimensions = 384", name="ck_embeddings_dimensions"),
        sa.CheckConstraint(
            "token_count > 0 AND embedded_token_count > 0 AND embedded_token_count <= token_count",
            name="ck_embeddings_token_counts",
        ),
        sa.CheckConstraint(
            "truncated = (embedded_token_count < token_count)",
            name="ck_embeddings_truncated",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_article_embeddings"),
        sa.UniqueConstraint(
            "article_version_id",
            "input_hash",
            "model_name",
            "model_version",
            name="uq_article_embeddings_input_model",
        ),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_article_embeddings_article_created",
        "article_embeddings",
        ["article_version_id", "created_at"],
        schema=SCHEMA_NAME,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_article_embeddings_article_created",
        table_name="article_embeddings",
        schema=SCHEMA_NAME,
    )
    op.drop_table("article_embeddings", schema=SCHEMA_NAME)
