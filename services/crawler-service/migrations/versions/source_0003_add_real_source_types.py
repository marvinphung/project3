"""Allow sitemap and HTML listing sources for the real crawler runner."""

from alembic import op

revision = "source_0003"
down_revision = "source_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_sources_source_type", "sources", schema="source_schema", type_="check")
    op.create_check_constraint(
        "ck_sources_source_type",
        "sources",
        "source_type IN ('RSS', 'SITEMAP', 'HTML', 'MOCK')",
        schema="source_schema",
    )


def downgrade() -> None:
    op.drop_constraint("ck_sources_source_type", "sources", schema="source_schema", type_="check")
    op.create_check_constraint(
        "ck_sources_source_type",
        "sources",
        "source_type IN ('RSS', 'MOCK')",
        schema="source_schema",
    )
