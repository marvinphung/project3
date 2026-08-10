"""Add immutable Story candidate matching audit tables.

Revision ID: intelligence_0006
Revises: intelligence_0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "intelligence_0006"
down_revision: str | None = "intelligence_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA_NAME = "intelligence_schema"


def upgrade() -> None:
    op.create_table(
        "story_match_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("article_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("candidate_set_hash", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("selected_story_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("selected_story_version", sa.Integer(), nullable=True),
        sa.Column("review_threshold", sa.Numeric(precision=6, scale=3), nullable=False),
        sa.Column("attach_threshold", sa.Numeric(precision=6, scale=3), nullable=False),
        sa.Column("near_tie_margin", sa.Numeric(precision=6, scale=3), nullable=False),
        sa.Column("matcher_version", sa.String(length=100), nullable=False),
        sa.Column("embedding_model_name", sa.String(length=200), nullable=False),
        sa.Column("embedding_model_version", sa.String(length=200), nullable=False),
        sa.Column("reason_codes", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "input_hash ~ '^[0-9a-f]{64}$'",
            name="ck_story_match_decisions_input_hash",
        ),
        sa.CheckConstraint(
            "candidate_set_hash ~ '^[0-9a-f]{64}$'",
            name="ck_story_match_decisions_candidate_hash",
        ),
        sa.CheckConstraint(
            "action IN ('ATTACH', 'CREATE', 'REVIEW')",
            name="ck_story_match_decisions_action",
        ),
        sa.CheckConstraint(
            "(action = 'CREATE' AND selected_story_id IS NULL "
            "AND selected_story_version IS NULL) OR "
            "(action IN ('ATTACH', 'REVIEW') AND selected_story_id IS NOT NULL "
            "AND selected_story_version >= 1)",
            name="ck_story_match_decisions_selection",
        ),
        sa.CheckConstraint(
            "review_threshold >= 0 AND review_threshold < attach_threshold "
            "AND attach_threshold <= 100",
            name="ck_story_match_decisions_thresholds",
        ),
        sa.CheckConstraint(
            "near_tie_margin >= 0 AND near_tie_margin <= 100",
            name="ck_story_match_decisions_margin",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(reason_codes) = 'array'",
            name="ck_story_match_decisions_reasons",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_story_match_decisions"),
        sa.UniqueConstraint(
            "article_version_id",
            "input_hash",
            "candidate_set_hash",
            "matcher_version",
            "embedding_model_name",
            "embedding_model_version",
            "review_threshold",
            "attach_threshold",
            "near_tie_margin",
            name="uq_story_match_decisions_input_matcher",
        ),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_story_match_decisions_article",
        "story_match_decisions",
        ["article_version_id", "created_at"],
        schema=SCHEMA_NAME,
    )

    op.create_table(
        "story_match_candidate_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rank", sa.SmallInteger(), nullable=False),
        sa.Column("story_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("story_version", sa.Integer(), nullable=False),
        sa.Column("total_score", sa.Numeric(precision=6, scale=3), nullable=False),
        sa.Column(
            "vector_similarity_score", sa.Numeric(precision=6, scale=3), nullable=False
        ),
        sa.Column("primary_entity_score", sa.Numeric(precision=6, scale=3), nullable=False),
        sa.Column("entity_overlap_score", sa.Numeric(precision=6, scale=3), nullable=False),
        sa.Column(
            "predicate_compatibility_score",
            sa.Numeric(precision=6, scale=3),
            nullable=False,
        ),
        sa.Column("time_distance_score", sa.Numeric(precision=6, scale=3), nullable=False),
        sa.Column("reason_codes", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["decision_id"],
            [f"{SCHEMA_NAME}.story_match_decisions.id"],
            name="fk_story_match_candidate_scores_decision",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("rank BETWEEN 1 AND 20", name="ck_story_match_scores_rank"),
        sa.CheckConstraint("story_version >= 1", name="ck_story_match_scores_version"),
        sa.CheckConstraint(
            "total_score >= 0 AND total_score <= 100",
            name="ck_story_match_scores_total",
        ),
        sa.CheckConstraint(
            "vector_similarity_score BETWEEN 0 AND 30 "
            "AND primary_entity_score BETWEEN 0 AND 25 "
            "AND entity_overlap_score BETWEEN 0 AND 15 "
            "AND predicate_compatibility_score BETWEEN 0 AND 20 "
            "AND time_distance_score BETWEEN 0 AND 10",
            name="ck_story_match_scores_components",
        ),
        sa.CheckConstraint(
            "total_score = vector_similarity_score + primary_entity_score "
            "+ entity_overlap_score + predicate_compatibility_score "
            "+ time_distance_score",
            name="ck_story_match_scores_component_total",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(reason_codes) = 'array'",
            name="ck_story_match_scores_reasons",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_story_match_candidate_scores"),
        sa.UniqueConstraint(
            "decision_id",
            "rank",
            name="uq_story_match_candidate_scores_rank",
        ),
        sa.UniqueConstraint(
            "decision_id",
            "story_id",
            name="uq_story_match_candidate_scores_story",
        ),
        schema=SCHEMA_NAME,
    )


def downgrade() -> None:
    op.drop_table("story_match_candidate_scores", schema=SCHEMA_NAME)
    op.drop_index(
        "ix_story_match_decisions_article",
        table_name="story_match_decisions",
        schema=SCHEMA_NAME,
    )
    op.drop_table("story_match_decisions", schema=SCHEMA_NAME)
