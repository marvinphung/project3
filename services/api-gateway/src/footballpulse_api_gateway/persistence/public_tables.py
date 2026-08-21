from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

public_metadata = sa.MetaData()

sources = sa.Table(
    "sources",
    public_metadata,
    sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("name", sa.Text(), nullable=False),
    sa.Column("domain_name", sa.Text(), nullable=False, unique=True),
    sa.Column("homepage_url", sa.Text()),
    sa.Column("reliability_tier", sa.SmallInteger(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

entities = sa.Table(
    "entities",
    public_metadata,
    sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("entity_type", sa.String(length=32), nullable=False),
    sa.Column("canonical_name", sa.Text(), nullable=False),
    sa.Column("slug", sa.String(length=200), nullable=False),
    sa.Column("aliases", postgresql.ARRAY(sa.Text()), nullable=False, default=[]),
    sa.Column("mention_count_24h", sa.Integer(), nullable=False, default=0),
    sa.Column("last_seen_at", sa.DateTime(timezone=True)),
    sa.Column("metadata", postgresql.JSONB(), nullable=False, default={}),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

source_articles = sa.Table(
    "source_articles",
    public_metadata,
    sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("title", sa.Text(), nullable=False),
    sa.Column("url", sa.Text(), nullable=False),
    sa.Column("canonical_url", sa.Text(), nullable=False, unique=True),
    sa.Column("source_name", sa.Text(), nullable=False),
    sa.Column("domain_name", sa.Text(), nullable=False),
    sa.Column("description", sa.Text()),
    sa.Column("image_url", sa.Text()),
    sa.Column("published_at", sa.DateTime(timezone=True)),
    sa.Column("crawled_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("content_hash", sa.Text()),
    sa.Column("slug", sa.Text()),
    sa.Column("body", sa.Text()),
    sa.Column("excerpt", sa.Text()),
    sa.Column("language", sa.Text(), nullable=False, server_default="en"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

entity_timeline_items = sa.Table(
    "entity_timeline_items",
    public_metadata,
    sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id"), nullable=False),
    sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
    sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
    sa.Column("title", sa.Text(), nullable=False),
    sa.Column("summary", sa.Text(), nullable=False),
    sa.Column("article_count", sa.Integer(), nullable=False),
    sa.Column("key_entities_50", postgresql.ARRAY(sa.Text()), nullable=False, default=[]),
    sa.Column("key_entities_80", postgresql.ARRAY(sa.Text()), nullable=False, default=[]),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

timeline_item_articles = sa.Table(
    "timeline_item_articles",
    public_metadata,
    sa.Column(
        "timeline_item_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("entity_timeline_items.id"),
        primary_key=True,
    ),
    sa.Column(
        "article_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("source_articles.id"),
        primary_key=True,
    ),
    sa.Column("position", sa.Integer(), nullable=False, default=0),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)
