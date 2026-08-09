from __future__ import annotations

import sqlalchemy as sa
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
