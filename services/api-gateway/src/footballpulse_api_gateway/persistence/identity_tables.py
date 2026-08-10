from __future__ import annotations

import sqlalchemy as sa

identity_metadata = sa.MetaData(schema="identity_schema")

users = sa.Table(
    "users",
    identity_metadata,
    sa.Column("username", sa.String(length=100), primary_key=True),
    sa.Column("password_hash", sa.Text(), nullable=False),
    sa.Column("role", sa.String(length=16), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("role IN ('EDITOR', 'ADMIN')", name="ck_users_role"),
)
