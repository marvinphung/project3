"""Create and seed the canonical entity catalog.

Revision ID: intelligence_0001
Revises:
"""

# ruff: noqa: E501 -- fixed seed SQL stays tabular and reviewable.

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "intelligence_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA_NAME = "intelligence_schema"


def upgrade() -> None:
    op.execute(sa.text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME}"))
    op.create_table(
        "entities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("canonical_name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="ACTIVE", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "entity_type IN ('PLAYER', 'CLUB', 'COACH', 'COMPETITION')",
            name="ck_entities_type",
        ),
        sa.CheckConstraint("status IN ('ACTIVE', 'DISABLED')", name="ck_entities_status"),
        sa.CheckConstraint("version > 0", name="ck_entities_version"),
        sa.CheckConstraint(
            "slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'",
            name="ck_entities_stable_slug",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_entities"),
        sa.UniqueConstraint("slug", name="uq_entities_slug"),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_entities_type_status_name",
        "entities",
        ["entity_type", "status", "canonical_name"],
        schema=SCHEMA_NAME,
    )

    op.create_table(
        "entity_aliases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "review_status IN ('PENDING_REVIEW', 'APPROVED', 'REJECTED')",
            name="ck_entity_aliases_review_status",
        ),
        sa.CheckConstraint(
            "source IN ('SEED', 'ADMIN', 'PIPELINE')", name="ck_entity_aliases_source"
        ),
        sa.CheckConstraint("version > 0", name="ck_entity_aliases_version"),
        sa.ForeignKeyConstraint(
            ["entity_id"],
            [f"{SCHEMA_NAME}.entities.id"],
            name="fk_entity_aliases_entity_id_entities",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_entity_aliases"),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "uq_entity_aliases_resolvable_normalized",
        "entity_aliases",
        ["normalized_alias"],
        unique=True,
        schema=SCHEMA_NAME,
        postgresql_where=sa.text("review_status = 'APPROVED' AND disabled_at IS NULL"),
    )
    op.create_index(
        "ix_entity_aliases_entity_status",
        "entity_aliases",
        ["entity_id", "review_status"],
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_entity_aliases_review_queue",
        "entity_aliases",
        ["review_status", "created_at"],
        schema=SCHEMA_NAME,
    )

    op.create_table(
        "entity_audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resource_type", sa.String(length=32), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("actor", sa.String(length=200), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "details", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "resource_type IN ('ENTITY', 'ALIAS')", name="ck_entity_audit_resource_type"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_entity_audit_log"),
        schema=SCHEMA_NAME,
    )
    op.create_index(
        "ix_entity_audit_resource_occurred",
        "entity_audit_log",
        ["resource_type", "resource_id", "occurred_at"],
        schema=SCHEMA_NAME,
    )

    op.execute(
        sa.text(
            f"""
            INSERT INTO {SCHEMA_NAME}.entities
                (id, entity_type, canonical_name, slug, status, version)
            VALUES
                ('018f8b45-b634-7c81-a47d-9a7c2f3c8101', 'PLAYER', 'Vinícius Júnior', 'vinicius-junior', 'ACTIVE', 1),
                ('018f8b45-b634-7c81-a47d-9a7c2f3c8102', 'CLUB', 'Real Madrid', 'real-madrid', 'ACTIVE', 1),
                ('018f8b45-b634-7c81-a47d-9a7c2f3c8103', 'CLUB', 'Arsenal', 'arsenal', 'ACTIVE', 1),
                ('018f8b45-b634-7c81-a47d-9a7c2f3c8104', 'COACH', 'Xabi Alonso', 'xabi-alonso', 'ACTIVE', 1),
                ('018f8b45-b634-7c81-a47d-9a7c2f3c8105', 'COMPETITION', 'La Liga', 'la-liga', 'ACTIVE', 1)
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            INSERT INTO {SCHEMA_NAME}.entity_aliases
                (id, entity_id, alias, normalized_alias, review_status,
                 resolver_version, source, created_by, reviewed_by, reviewed_at, version)
            VALUES
                ('018f8b45-b634-7c81-a47d-9a7c2f3c8201', '018f8b45-b634-7c81-a47d-9a7c2f3c8101', 'Vinícius Júnior', 'vinicius junior', 'APPROVED', 'seed-v1', 'SEED', 'system:seed', 'system:seed', now(), 1),
                ('018f8b45-b634-7c81-a47d-9a7c2f3c8202', '018f8b45-b634-7c81-a47d-9a7c2f3c8101', 'Vini Jr', 'vini jr', 'APPROVED', 'seed-v1', 'SEED', 'system:seed', 'system:seed', now(), 1),
                ('018f8b45-b634-7c81-a47d-9a7c2f3c8203', '018f8b45-b634-7c81-a47d-9a7c2f3c8102', 'Real Madrid', 'real madrid', 'APPROVED', 'seed-v1', 'SEED', 'system:seed', 'system:seed', now(), 1),
                ('018f8b45-b634-7c81-a47d-9a7c2f3c8204', '018f8b45-b634-7c81-a47d-9a7c2f3c8103', 'Arsenal', 'arsenal', 'APPROVED', 'seed-v1', 'SEED', 'system:seed', 'system:seed', now(), 1),
                ('018f8b45-b634-7c81-a47d-9a7c2f3c8205', '018f8b45-b634-7c81-a47d-9a7c2f3c8103', 'Gunners', 'gunners', 'APPROVED', 'seed-v1', 'SEED', 'system:seed', 'system:seed', now(), 1),
                ('018f8b45-b634-7c81-a47d-9a7c2f3c8206', '018f8b45-b634-7c81-a47d-9a7c2f3c8104', 'Xabi Alonso', 'xabi alonso', 'APPROVED', 'seed-v1', 'SEED', 'system:seed', 'system:seed', now(), 1),
                ('018f8b45-b634-7c81-a47d-9a7c2f3c8207', '018f8b45-b634-7c81-a47d-9a7c2f3c8105', 'La Liga', 'la liga', 'APPROVED', 'seed-v1', 'SEED', 'system:seed', 'system:seed', now(), 1)
            """
        )
    )


def downgrade() -> None:
    op.drop_index(
        "ix_entity_audit_resource_occurred",
        table_name="entity_audit_log",
        schema=SCHEMA_NAME,
    )
    op.drop_table("entity_audit_log", schema=SCHEMA_NAME)
    op.drop_index("ix_entity_aliases_review_queue", table_name="entity_aliases", schema=SCHEMA_NAME)
    op.drop_index(
        "ix_entity_aliases_entity_status", table_name="entity_aliases", schema=SCHEMA_NAME
    )
    op.drop_index(
        "uq_entity_aliases_resolvable_normalized",
        table_name="entity_aliases",
        schema=SCHEMA_NAME,
    )
    op.drop_table("entity_aliases", schema=SCHEMA_NAME)
    op.drop_index("ix_entities_type_status_name", table_name="entities", schema=SCHEMA_NAME)
    op.drop_table("entities", schema=SCHEMA_NAME)
