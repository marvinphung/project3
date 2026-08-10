from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

content_metadata = sa.MetaData(schema="content_schema")
intelligence_metadata = sa.MetaData(schema="intelligence_schema")

entities = sa.Table(
    "entities",
    intelligence_metadata,
    sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("entity_type", sa.String(length=32), nullable=False),
    sa.Column("slug", sa.String(length=200), nullable=False),
)

story_entities = sa.Table(
    "story_entities",
    intelligence_metadata,
    sa.Column("story_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
)

publications = sa.Table(
    "publications",
    content_metadata,
    sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("generated_article_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("revision_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("story_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("story_version", sa.Integer(), nullable=False),
    sa.Column("slug", sa.String(length=200), nullable=False),
    sa.Column("title_en", sa.Text(), nullable=False),
    sa.Column("body_en", sa.Text(), nullable=False),
    sa.Column("title_vi", sa.Text(), nullable=False),
    sa.Column("body_vi", sa.Text(), nullable=False),
    sa.Column("idempotency_key", sa.String(length=200), nullable=False),
    sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
)

timeline_entries = sa.Table(
    "timeline_entries",
    intelligence_metadata,
    sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("story_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
    sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
    sa.Column("summary_en", sa.Text(), nullable=False),
    sa.Column("summary_vi", sa.Text(), nullable=False),
    sa.Column("confirmation", sa.String(length=16), nullable=False),
    sa.Column("used_claim_ids", postgresql.JSONB(), nullable=False),
    sa.Column("source_article_ids", postgresql.JSONB(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)
