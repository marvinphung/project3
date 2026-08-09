"""Create source owner crawl tables.

Revision ID: source_0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "source_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA_NAME = "source_schema"


def upgrade() -> None:
    op.execute(sa.text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME}"))
    op.create_table(
        "sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("rss_url", sa.Text(), nullable=False),
        sa.Column("allowed_domains", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("reliability_tier", sa.SmallInteger(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("crawl_interval_minutes", sa.Integer(), server_default="360", nullable=False),
        sa.Column("max_concurrency", sa.SmallInteger(), server_default="2", nullable=False),
        sa.Column("last_discovered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("cardinality(allowed_domains) > 0", name="ck_sources_allowed_domains"),
        sa.CheckConstraint("source_type IN ('RSS', 'MOCK')", name="ck_sources_source_type"),
        sa.CheckConstraint("reliability_tier BETWEEN 1 AND 5", name="ck_sources_reliability_tier"),
        sa.CheckConstraint("crawl_interval_minutes > 0", name="ck_sources_crawl_interval"),
        sa.CheckConstraint("max_concurrency > 0", name="ck_sources_max_concurrency"),
        sa.PrimaryKeyConstraint("id", name="pk_sources"),
        sa.UniqueConstraint("rss_url", name="uq_sources_rss_url"),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_sources_enabled",
        "sources",
        ["enabled"],
        unique=False,
        schema=SCHEMA_NAME,
    )

    op.create_table(
        "crawl_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("discovered_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("fetched_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'COMPLETED', 'PARTIAL', 'FAILED')",
            name="ck_crawl_batches_status",
        ),
        sa.CheckConstraint(
            "discovered_count >= 0 AND fetched_count >= 0 AND failed_count >= 0",
            name="ck_crawl_batches_counts",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            [f"{SCHEMA_NAME}.sources.id"],
            name="fk_crawl_batches_source_id_sources",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_crawl_batches"),
        sa.UniqueConstraint(
            "source_id", "window_started_at", name="uq_crawl_batches_source_window"
        ),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_crawl_batches_status_window",
        "crawl_batches",
        ["status", "window_started_at"],
        unique=False,
        schema=SCHEMA_NAME,
    )

    op.create_table(
        "crawl_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("article_url", sa.Text(), nullable=False),
        sa.Column("attempt_number", sa.SmallInteger(), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("http_status", sa.SmallInteger(), nullable=True),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("failure_detail_redacted", sa.Text(), nullable=True),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("attempt_number > 0", name="ck_crawl_attempts_attempt_number"),
        sa.CheckConstraint(
            "outcome IN ('PENDING', 'SUCCEEDED', 'RETRYABLE_FAILURE', 'PERMANENT_FAILURE')",
            name="ck_crawl_attempts_outcome",
        ),
        sa.CheckConstraint(
            "http_status IS NULL OR http_status BETWEEN 100 AND 599",
            name="ck_crawl_attempts_http_status",
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            [f"{SCHEMA_NAME}.crawl_batches.id"],
            name="fk_crawl_attempts_batch_id_crawl_batches",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_crawl_attempts"),
        sa.UniqueConstraint(
            "batch_id", "article_url", "attempt_number", name="uq_crawl_attempts_batch_url_attempt"
        ),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_crawl_attempts_outcome_started",
        "crawl_attempts",
        ["outcome", "started_at"],
        unique=False,
        schema=SCHEMA_NAME,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_crawl_attempts_outcome_started", table_name="crawl_attempts", schema=SCHEMA_NAME
    )
    op.drop_table("crawl_attempts", schema=SCHEMA_NAME)
    op.drop_index("ix_crawl_batches_status_window", table_name="crawl_batches", schema=SCHEMA_NAME)
    op.drop_table("crawl_batches", schema=SCHEMA_NAME)
    op.drop_index("ix_sources_enabled", table_name="sources", schema=SCHEMA_NAME)
    op.drop_table("sources", schema=SCHEMA_NAME)
