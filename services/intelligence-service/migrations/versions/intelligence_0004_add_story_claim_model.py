"""Add Story, Claim, evidence and reliable event delivery tables.

Revision ID: intelligence_0004
Revises: intelligence_0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "intelligence_0004"
down_revision: str | None = "intelligence_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA_NAME = "intelligence_schema"


def upgrade() -> None:
    op.create_table(
        "stories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("confidence_score", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('DEVELOPING', 'CONFIRMED', 'STALE', 'CLOSED')",
            name="ck_stories_status",
        ),
        sa.CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="ck_stories_confidence_score",
        ),
        sa.CheckConstraint("last_seen_at >= first_seen_at", name="ck_stories_seen_range"),
        sa.CheckConstraint("version >= 1", name="ck_stories_version"),
        sa.PrimaryKeyConstraint("id", name="pk_stories"),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_stories_status_last_seen",
        "stories",
        ["status", "last_seen_at"],
        schema=SCHEMA_NAME,
    )

    op.create_table(
        "story_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("story_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("article_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_reliability_tier", sa.SmallInteger(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["story_id"],
            [f"{SCHEMA_NAME}.stories.id"],
            name="fk_story_sources_story",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "source_reliability_tier BETWEEN 1 AND 5",
            name="ck_story_sources_reliability_tier",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_story_sources"),
        sa.UniqueConstraint(
            "story_id",
            "article_version_id",
            name="uq_story_sources_article",
        ),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_story_sources_article_version",
        "story_sources",
        ["article_version_id"],
        schema=SCHEMA_NAME,
    )

    op.create_table(
        "story_entities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("story_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["story_id"],
            [f"{SCHEMA_NAME}.stories.id"],
            name="fk_story_entities_story",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["entity_id"],
            [f"{SCHEMA_NAME}.entities.id"],
            name="fk_story_entities_entity",
        ),
        sa.CheckConstraint(
            "entity_type IN ('PLAYER', 'CLUB', 'COACH', 'COMPETITION')",
            name="ck_story_entities_type",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_story_entities"),
        sa.UniqueConstraint("story_id", "entity_id", name="uq_story_entities_entity"),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_story_entities_entity",
        "story_entities",
        ["entity_id", "story_id"],
        schema=SCHEMA_NAME,
    )

    op.create_table(
        "claims",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["story_id"],
            [f"{SCHEMA_NAME}.stories.id"],
            name="fk_claims_story",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["subject_entity_id"],
            [f"{SCHEMA_NAME}.entities.id"],
            name="fk_claims_subject_entity",
        ),
        sa.ForeignKeyConstraint(
            ["object_entity_id"],
            [f"{SCHEMA_NAME}.entities.id"],
            name="fk_claims_object_entity",
        ),
        sa.CheckConstraint(
            "claim_fingerprint ~ '^[0-9a-f]{64}$'",
            name="ck_claims_fingerprint",
        ),
        sa.CheckConstraint("length(trim(statement_en)) > 0", name="ck_claims_statement"),
        sa.CheckConstraint("certainty >= 0 AND certainty <= 1", name="ck_claims_certainty"),
        sa.CheckConstraint(
            "object_entity_id IS NOT NULL OR object_value IS NOT NULL",
            name="ck_claims_object",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_claims"),
        sa.UniqueConstraint("story_id", "claim_fingerprint", name="uq_claims_fingerprint"),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_claims_story_occurred",
        "claims",
        ["story_id", "occurred_at"],
        schema=SCHEMA_NAME,
    )

    op.create_table(
        "claim_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("story_source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_quote", sa.Text(), nullable=False),
        sa.Column("evidence_start", sa.Integer(), nullable=False),
        sa.Column("evidence_end", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["claim_id"],
            [f"{SCHEMA_NAME}.claims.id"],
            name="fk_claim_evidence_claim",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["story_source_id"],
            [f"{SCHEMA_NAME}.story_sources.id"],
            name="fk_claim_evidence_story_source",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("length(trim(evidence_quote)) > 0", name="ck_claim_evidence_quote"),
        sa.CheckConstraint(
            "evidence_start >= 0 AND evidence_end > evidence_start",
            name="ck_claim_evidence_range",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_claim_evidence"),
        sa.UniqueConstraint(
            "claim_id",
            "story_source_id",
            "evidence_start",
            "evidence_end",
            name="uq_claim_evidence_range",
        ),
        schema=SCHEMA_NAME,
    )

    op.create_table(
        "processed_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consumer_name", sa.String(length=100), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column(
            "processed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_processed_events"),
        sa.UniqueConstraint(
            "consumer_name",
            "event_id",
            name="uq_processed_events_consumer_event",
        ),
        schema=SCHEMA_NAME,
    )

    op.create_table(
        "outbox_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("aggregate_type", sa.String(length=64), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("deduplication_key", sa.String(length=200), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="PENDING", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "available_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'PUBLISHED', 'FAILED')", name="ck_outbox_events_status"
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_outbox_events_attempt_count"),
        sa.PrimaryKeyConstraint("id", name="pk_outbox_events"),
        sa.UniqueConstraint("deduplication_key", name="uq_outbox_events_deduplication_key"),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_outbox_events_delivery",
        "outbox_events",
        ["status", "available_at", "created_at"],
        schema=SCHEMA_NAME,
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_events_delivery", table_name="outbox_events", schema=SCHEMA_NAME)
    op.drop_table("outbox_events", schema=SCHEMA_NAME)
    op.drop_table("processed_events", schema=SCHEMA_NAME)
    op.drop_table("claim_evidence", schema=SCHEMA_NAME)
    op.drop_index("ix_claims_story_occurred", table_name="claims", schema=SCHEMA_NAME)
    op.drop_table("claims", schema=SCHEMA_NAME)
    op.drop_index("ix_story_entities_entity", table_name="story_entities", schema=SCHEMA_NAME)
    op.drop_table("story_entities", schema=SCHEMA_NAME)
    op.drop_index(
        "ix_story_sources_article_version",
        table_name="story_sources",
        schema=SCHEMA_NAME,
    )
    op.drop_table("story_sources", schema=SCHEMA_NAME)
    op.drop_index("ix_stories_status_last_seen", table_name="stories", schema=SCHEMA_NAME)
    op.drop_table("stories", schema=SCHEMA_NAME)
