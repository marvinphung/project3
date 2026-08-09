from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

metadata = sa.MetaData(schema="source_schema")

sources = sa.Table(
    "sources",
    metadata,
    sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("name", sa.String(length=200), nullable=False),
    sa.Column("rss_url", sa.Text(), nullable=False),
    sa.Column("allowed_domains", postgresql.ARRAY(sa.Text()), nullable=False),
    sa.Column("source_type", sa.String(length=32), nullable=False),
    sa.Column("reliability_tier", sa.SmallInteger(), nullable=False),
    sa.Column("enabled", sa.Boolean(), nullable=False),
    sa.Column("crawl_interval_minutes", sa.Integer(), nullable=False),
    sa.Column("max_concurrency", sa.SmallInteger(), nullable=False),
    sa.Column("last_discovered_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("version", sa.Integer(), nullable=False),
)

crawl_batches = sa.Table(
    "crawl_batches",
    metadata,
    sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("idempotency_key", sa.String(length=256), nullable=False),
    sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("status", sa.String(length=32), nullable=False),
    sa.Column("discovered_count", sa.Integer(), nullable=False),
    sa.Column("fetched_count", sa.Integer(), nullable=False),
    sa.Column("failed_count", sa.Integer(), nullable=False),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
)
