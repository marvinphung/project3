"""Remove obsolete mock sources from the crawler catalog."""

from __future__ import annotations

from alembic import op


revision = "source_0004"
down_revision = "source_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DELETE FROM source_schema.sources WHERE source_type = 'MOCK'")
    op.drop_constraint("ck_sources_source_type", "sources", schema="source_schema", type_="check")
    op.create_check_constraint(
        "ck_sources_source_type",
        "sources",
        "source_type IN ('RSS', 'SITEMAP', 'HTML')",
        schema="source_schema",
    )


def downgrade() -> None:
    op.drop_constraint("ck_sources_source_type", "sources", schema="source_schema", type_="check")
    op.create_check_constraint(
        "ck_sources_source_type",
        "sources",
        "source_type IN ('RSS', 'SITEMAP', 'HTML', 'MOCK')",
        schema="source_schema",
    )
