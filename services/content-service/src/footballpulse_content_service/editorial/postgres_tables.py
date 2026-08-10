from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

metadata = sa.MetaData(schema="content_schema")

editorial_revisions = sa.Table(
    "editorial_revisions",
    metadata,
    sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("generated_article_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("story_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("story_version", sa.Integer(), nullable=False),
    sa.Column("revision_number", sa.Integer(), nullable=False),
    sa.Column("title_en", sa.Text(), nullable=False),
    sa.Column("body_en", sa.Text(), nullable=False),
    sa.Column("title_vi", sa.Text(), nullable=False),
    sa.Column("body_vi", sa.Text(), nullable=False),
    sa.Column("state", sa.String(length=32), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

publications = sa.Table(
    "publications",
    metadata,
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

publication_outbox = sa.Table(
    "publication_outbox",
    metadata,
    sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("publication_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("topic", sa.String(length=100), nullable=False),
    sa.Column("message_key", sa.String(length=200), nullable=False),
    sa.Column("payload", postgresql.JSONB(), nullable=False),
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("state", sa.String(length=16), nullable=False),
    sa.Column("attempt_count", sa.Integer(), nullable=False),
    sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("last_error", sa.Text(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)
