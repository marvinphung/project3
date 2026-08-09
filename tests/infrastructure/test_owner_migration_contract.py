from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]

OWNER_MIGRATIONS = {
    "crawler-service": ("source_schema", "alembic_version_source"),
    "api-gateway": ("identity_schema", "alembic_version_identity"),
    "intelligence-service": ("intelligence_schema", "alembic_version_intelligence"),
}


@pytest.mark.parametrize(
    ("service", "schema_name", "version_table"),
    [(service, *contract) for service, contract in OWNER_MIGRATIONS.items()],
)
def test_each_database_owner_has_an_independent_alembic_environment(
    service: str,
    schema_name: str,
    version_table: str,
) -> None:
    migration_root = ROOT / "services" / service / "migrations"
    config = (ROOT / "services" / service / "alembic.ini").read_text()
    environment = (migration_root / "env.py").read_text()

    assert (migration_root / "versions").is_dir()
    assert "script_location = %(here)s/migrations" in config
    assert f'SCHEMA_NAME = "{schema_name}"' in environment
    assert f'VERSION_TABLE = "{version_table}"' in environment
    assert "version_table=VERSION_TABLE" in environment
    assert "version_table_schema=SCHEMA_NAME" in environment


@pytest.mark.parametrize(
    ("service", "owned_schema", "foreign_schema"),
    [
        ("crawler-service", "source_schema", "identity_schema"),
        ("api-gateway", "identity_schema", "source_schema"),
        ("intelligence-service", "intelligence_schema", "source_schema"),
    ],
)
def test_owner_migrations_render_schema_qualified_sql_without_cross_owner_references(
    service: str,
    owned_schema: str,
    foreign_schema: str,
) -> None:
    result = subprocess.run(
        [
            "uv",
            "run",
            "alembic",
            "-c",
            f"services/{service}/alembic.ini",
            "upgrade",
            "head",
            "--sql",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert f"CREATE SCHEMA IF NOT EXISTS {owned_schema}" in result.stdout
    assert f"{foreign_schema}." not in result.stdout


def test_source_migrations_add_optimistic_version_and_batch_idempotency() -> None:
    migration = (
        ROOT / "services/crawler-service/migrations/versions/source_0002_add_source_concurrency.py"
    ).read_text()

    assert '"version"' in migration
    assert '"idempotency_key"' in migration
    assert "uq_crawl_batches_idempotency_key" in migration


def test_intelligence_migration_seeds_reviewed_mvp_entities_and_aliases() -> None:
    migration = (
        ROOT
        / "services/intelligence-service/migrations/versions/"
        / "intelligence_0001_create_entity_catalog.py"
    ).read_text()

    for value in ("Vinícius Júnior", "Real Madrid", "Arsenal", "Xabi Alonso", "La Liga"):
        assert value in migration
    assert "uq_entity_aliases_resolvable_normalized" in migration
    assert "PENDING_REVIEW" in migration
    assert "entity_audit_log" in migration


def test_intelligence_migration_adds_unresolved_review_queue() -> None:
    migration = (
        ROOT
        / "services/intelligence-service/migrations/versions/"
        / "intelligence_0002_add_unresolved_entity_mentions.py"
    ).read_text()

    assert "unresolved_entity_mentions" in migration
    assert "PENDING_REVIEW" in migration
    assert "article_version_id" in migration
    assert "resolved_entity_id" in migration
