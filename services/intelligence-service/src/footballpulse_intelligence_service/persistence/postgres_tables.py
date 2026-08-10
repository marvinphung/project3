from __future__ import annotations

import sqlalchemy as sa
from pgvector.sqlalchemy import VECTOR
from sqlalchemy.dialects import postgresql

metadata = sa.MetaData(schema="intelligence_schema")

entities = sa.Table(
    "entities",
    metadata,
    sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("entity_type", sa.String(length=32), nullable=False),
    sa.Column("canonical_name", sa.String(length=200), nullable=False),
    sa.Column("slug", sa.String(length=200), nullable=False),
    sa.Column("status", sa.String(length=32), nullable=False),
    sa.Column("version", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

entity_aliases = sa.Table(
    "entity_aliases",
    metadata,
    sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("alias", sa.String(length=200), nullable=False),
    sa.Column("normalized_alias", sa.String(length=200), nullable=False),
    sa.Column("review_status", sa.String(length=32), nullable=False),
    sa.Column("resolver_version", sa.String(length=100), nullable=False),
    sa.Column("source", sa.String(length=32), nullable=False),
    sa.Column("created_by", sa.String(length=200), nullable=False),
    sa.Column("reviewed_by", sa.String(length=200), nullable=True),
    sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("version", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

entity_audit_log = sa.Table(
    "entity_audit_log",
    metadata,
    sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("resource_type", sa.String(length=32), nullable=False),
    sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("action", sa.String(length=64), nullable=False),
    sa.Column("actor", sa.String(length=200), nullable=False),
    sa.Column("reason", sa.Text(), nullable=False),
    sa.Column("details", postgresql.JSONB(), nullable=False),
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
)

unresolved_entity_mentions = sa.Table(
    "unresolved_entity_mentions",
    metadata,
    sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
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
    sa.Column("status", sa.String(length=32), nullable=False),
    sa.Column("resolved_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column("reviewed_by", sa.String(length=200), nullable=True),
    sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("resolution_note", sa.Text(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

article_embeddings = sa.Table(
    "article_embeddings",
    metadata,
    sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
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
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

stories = sa.Table(
    "stories",
    metadata,
    sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("event_type", sa.String(length=32), nullable=False),
    sa.Column("status", sa.String(length=32), nullable=False),
    sa.Column("confidence_score", sa.Numeric(precision=5, scale=4), nullable=False),
    sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("version", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

story_sources = sa.Table(
    "story_sources",
    metadata,
    sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("story_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("article_version_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("source_reliability_tier", sa.SmallInteger(), nullable=False),
    sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
)

story_entities = sa.Table(
    "story_entities",
    metadata,
    sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("story_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("entity_type", sa.String(length=32), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

claims = sa.Table(
    "claims",
    metadata,
    sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("story_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("claim_fingerprint", sa.String(length=64), nullable=False),
    sa.Column("subject_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("predicate", sa.String(length=64), nullable=False),
    sa.Column("object_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column("object_value", postgresql.JSONB(), nullable=True),
    sa.Column("statement_en", sa.Text(), nullable=False),
    sa.Column("certainty", sa.Numeric(precision=5, scale=4), nullable=False),
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("occurred_at_bucket", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

claim_evidence = sa.Table(
    "claim_evidence",
    metadata,
    sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("claim_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("story_source_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("evidence_quote", sa.Text(), nullable=False),
    sa.Column("evidence_start", sa.Integer(), nullable=False),
    sa.Column("evidence_end", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

processed_events = sa.Table(
    "processed_events",
    metadata,
    sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("consumer_name", sa.String(length=100), nullable=False),
    sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("event_type", sa.String(length=100), nullable=False),
    sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
)

outbox_events = sa.Table(
    "outbox_events",
    metadata,
    sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("aggregate_type", sa.String(length=64), nullable=False),
    sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("event_type", sa.String(length=100), nullable=False),
    sa.Column("deduplication_key", sa.String(length=200), nullable=False),
    sa.Column("payload", postgresql.JSONB(), nullable=False),
    sa.Column("status", sa.String(length=16), nullable=False),
    sa.Column("attempt_count", sa.Integer(), nullable=False),
    sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("last_error", sa.Text(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)
