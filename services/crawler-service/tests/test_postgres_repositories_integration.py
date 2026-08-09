from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from footballpulse_crawler_service.domain.crawl_batch import CrawlBatch, CrawlBatchStatus
from footballpulse_crawler_service.domain.errors import SourceConflictError
from footballpulse_crawler_service.domain.source import Source, SourceType
from footballpulse_crawler_service.persistence.postgres_repositories import (
    PostgresCrawlBatchRepository,
    PostgresSourceRepository,
)
from psycopg import sql
from sqlalchemy import create_engine

ROOT = Path(__file__).parents[3]
NOW = datetime(2026, 8, 1, tzinfo=UTC)


def postgres_url(database: str, *, sqlalchemy_driver: bool = False) -> str:
    scheme = "postgresql+psycopg" if sqlalchemy_driver else "postgresql"
    user = os.getenv("FOOTBALLPULSE_POSTGRES_USER", "footballpulse")
    password = os.getenv("FOOTBALLPULSE_POSTGRES_PASSWORD", "footballpulse_local_only")
    host = os.getenv("FOOTBALLPULSE_POSTGRES_HOST", "127.0.0.1")
    port = os.getenv("FOOTBALLPULSE_POSTGRES_PORT", "5432")
    return f"{scheme}://{user}:{password}@{host}:{port}/{database}"


@pytest.fixture
def migrated_database() -> Iterator[str]:
    database = f"footballpulse_source_test_{uuid4().hex}"
    with psycopg.connect(postgres_url("postgres"), autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    environment = os.environ.copy()
    environment["FOOTBALLPULSE_DATABASE_URL"] = postgres_url(database, sqlalchemy_driver=True)
    migration = subprocess.run(
        [
            "uv",
            "run",
            "alembic",
            "-c",
            "services/crawler-service/alembic.ini",
            "upgrade",
            "head",
        ],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert migration.returncode == 0, migration.stderr
    try:
        yield database
    finally:
        with psycopg.connect(postgres_url("postgres"), autocommit=True) as connection:
            connection.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (database,),
            )
            connection.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database)))


def make_source(source_id: UUID, *, rss_url: str = "https://www.bbc.com/rss.xml") -> Source:
    return Source(
        id=source_id,
        name="BBC Sport",
        rss_url=rss_url,
        allowed_domains=("bbc.com",),
        source_type=SourceType.RSS,
        reliability_tier=1,
        enabled=True,
        crawl_interval_minutes=360,
        max_concurrency=2,
        last_discovered_at=None,
        created_at=NOW,
        updated_at=NOW,
        version=1,
    )


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("FOOTBALLPULSE_RUN_SOURCE_INTEGRATION") != "1",
    reason="set FOOTBALLPULSE_RUN_SOURCE_INTEGRATION=1 with PostgreSQL running",
)
def test_source_and_batch_repositories_preserve_concurrency_and_idempotency(
    migrated_database: str,
) -> None:
    engine = create_engine(postgres_url(migrated_database, sqlalchemy_driver=True))
    sources = PostgresSourceRepository(engine)
    batches = PostgresCrawlBatchRepository(engine)
    source_id = UUID("00000000-0000-0000-0000-000000000101")
    source = sources.add(make_source(source_id))

    assert sources.get(source_id) == source
    assert sources.list_sources(limit=10, offset=0) == [source]
    assert sources.due(at=NOW, limit=10) == [source]
    with pytest.raises(SourceConflictError, match="RSS URL"):
        sources.add(make_source(uuid4()))

    disabled = source.with_enabled(False, now=NOW)
    assert sources.save(disabled, expected_version=1) == disabled
    with pytest.raises(SourceConflictError, match="version"):
        sources.save(source.with_enabled(False, now=NOW), expected_version=1)

    batch = CrawlBatch(
        id=UUID("00000000-0000-0000-0000-000000000201"),
        source_id=source_id,
        idempotency_key="bbc:2026-08-01T00:00:00Z",
        window_started_at=NOW,
        status=CrawlBatchStatus.RUNNING,
        discovered_count=0,
        fetched_count=0,
        failed_count=0,
        started_at=NOW,
        completed_at=None,
    )
    assert batches.open(batch) == batch
    assert batches.open(replace(batch, id=uuid4())) == batch
