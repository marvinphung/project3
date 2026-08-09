from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

ROOT = Path(__file__).parents[2]
SERVICES = ("crawler-service", "api-gateway", "intelligence-service")


def postgres_connection_url(database: str) -> str:
    user = os.getenv("FOOTBALLPULSE_POSTGRES_USER", "footballpulse")
    password = os.getenv("FOOTBALLPULSE_POSTGRES_PASSWORD", "footballpulse_local_only")
    host = os.getenv("FOOTBALLPULSE_POSTGRES_HOST", "127.0.0.1")
    port = os.getenv("FOOTBALLPULSE_POSTGRES_PORT", "5432")
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


@pytest.fixture
def empty_postgres_database() -> Iterator[str]:
    database = f"footballpulse_migration_test_{uuid4().hex}"
    with psycopg.connect(postgres_connection_url("postgres"), autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    try:
        yield database
    finally:
        with psycopg.connect(postgres_connection_url("postgres"), autocommit=True) as connection:
            connection.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (database,),
            )
            connection.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database)))


def run_alembic(
    service: str,
    command: str,
    target: str,
    database: str,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["FOOTBALLPULSE_DATABASE_URL"] = postgres_connection_url(database).replace(
        "postgresql://", "postgresql+psycopg://", 1
    )
    return subprocess.run(
        ["uv", "run", "alembic", "-c", f"services/{service}/alembic.ini", command, target],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("FOOTBALLPULSE_RUN_INTEGRATION") != "1",
    reason="set FOOTBALLPULSE_RUN_INTEGRATION=1 with PostgreSQL running",
)
def test_owner_migrations_upgrade_idempotently_and_downgrade_cleanly(
    empty_postgres_database: str,
) -> None:
    database = empty_postgres_database

    for service in SERVICES:
        first_upgrade = run_alembic(service, "upgrade", "head", database)
        assert first_upgrade.returncode == 0, first_upgrade.stderr
        second_upgrade = run_alembic(service, "upgrade", "head", database)
        assert second_upgrade.returncode == 0, second_upgrade.stderr

    with psycopg.connect(postgres_connection_url(database)) as connection:
        tables = set(
            connection.execute(
                "SELECT table_schema, table_name FROM information_schema.tables "
                "WHERE table_schema IN ('source_schema', 'identity_schema', "
                "'intelligence_schema')"
            ).fetchall()
        )
        assert {
            ("source_schema", "sources"),
            ("source_schema", "crawl_batches"),
            ("source_schema", "crawl_attempts"),
            ("source_schema", "alembic_version_source"),
            ("identity_schema", "alembic_version_identity"),
            ("intelligence_schema", "entities"),
            ("intelligence_schema", "entity_aliases"),
            ("intelligence_schema", "entity_audit_log"),
            ("intelligence_schema", "alembic_version_intelligence"),
        } <= tables
        seed_counts = connection.execute(
            "SELECT "
            "(SELECT count(*) FROM intelligence_schema.entities), "
            "(SELECT count(*) FROM intelligence_schema.entity_aliases)"
        ).fetchone()
        assert seed_counts == (5, 7)
        cross_owner_foreign_keys = connection.execute(
            "SELECT count(*) FROM pg_constraint c "
            "JOIN pg_class child ON child.oid = c.conrelid "
            "JOIN pg_namespace child_ns ON child_ns.oid = child.relnamespace "
            "JOIN pg_class parent ON parent.oid = c.confrelid "
            "JOIN pg_namespace parent_ns ON parent_ns.oid = parent.relnamespace "
            "WHERE c.contype = 'f' AND child_ns.nspname <> parent_ns.nspname "
            "AND child_ns.nspname IN "
            "('source_schema', 'identity_schema', 'intelligence_schema')"
        ).fetchone()
        assert cross_owner_foreign_keys == (0,)

    for service in reversed(SERVICES):
        downgrade = run_alembic(service, "downgrade", "base", database)
        assert downgrade.returncode == 0, downgrade.stderr

    with psycopg.connect(postgres_connection_url(database)) as connection:
        product_table_count = connection.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema IN ('source_schema', 'intelligence_schema') "
            "AND table_name IN "
            "('sources', 'crawl_batches', 'crawl_attempts', 'entities', "
            "'entity_aliases', 'entity_audit_log')"
        ).fetchone()
        assert product_table_count == (0,)
