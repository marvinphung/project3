from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine, RowMapping
from sqlalchemy.exc import IntegrityError

from footballpulse_crawler_service.domain.crawl_batch import CrawlBatch, CrawlBatchStatus
from footballpulse_crawler_service.domain.errors import SourceConflictError
from footballpulse_crawler_service.domain.source import Source, SourceType
from footballpulse_crawler_service.persistence.postgres_tables import crawl_batches, sources


def _source_values(source: Source) -> dict[str, object]:
    return {
        "id": source.id,
        "name": source.name,
        "rss_url": source.rss_url,
        "allowed_domains": list(source.allowed_domains),
        "source_type": source.source_type.value,
        "reliability_tier": source.reliability_tier,
        "enabled": source.enabled,
        "crawl_interval_minutes": source.crawl_interval_minutes,
        "max_concurrency": source.max_concurrency,
        "last_discovered_at": source.last_discovered_at,
        "created_at": source.created_at,
        "updated_at": source.updated_at,
        "version": source.version,
    }


def _source_from_row(row: RowMapping) -> Source:
    return Source(
        id=row["id"],
        name=row["name"],
        rss_url=row["rss_url"],
        allowed_domains=tuple(row["allowed_domains"]),
        source_type=SourceType(row["source_type"]),
        reliability_tier=row["reliability_tier"],
        enabled=row["enabled"],
        crawl_interval_minutes=row["crawl_interval_minutes"],
        max_concurrency=row["max_concurrency"],
        last_discovered_at=row["last_discovered_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        version=row["version"],
    )


def _batch_values(batch: CrawlBatch) -> dict[str, object]:
    return {
        "id": batch.id,
        "source_id": batch.source_id,
        "idempotency_key": batch.idempotency_key,
        "window_started_at": batch.window_started_at,
        "status": batch.status.value,
        "discovered_count": batch.discovered_count,
        "fetched_count": batch.fetched_count,
        "failed_count": batch.failed_count,
        "started_at": batch.started_at,
        "completed_at": batch.completed_at,
    }


def _batch_from_row(row: RowMapping) -> CrawlBatch:
    return CrawlBatch(
        id=row["id"],
        source_id=row["source_id"],
        idempotency_key=row["idempotency_key"],
        window_started_at=row["window_started_at"],
        status=CrawlBatchStatus(row["status"]),
        discovered_count=row["discovered_count"],
        fetched_count=row["fetched_count"],
        failed_count=row["failed_count"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
    )


class PostgresSourceRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def add(self, source: Source) -> Source:
        statement = sources.insert().values(**_source_values(source)).returning(*sources.c)
        try:
            with self._engine.begin() as connection:
                row = connection.execute(statement).mappings().one()
        except IntegrityError as exc:
            raise SourceConflictError("source RSS URL already exists") from exc
        return _source_from_row(row)

    def get(self, source_id: UUID) -> Source | None:
        statement = sa.select(sources).where(sources.c.id == source_id)
        with self._engine.connect() as connection:
            row = connection.execute(statement).mappings().one_or_none()
        return None if row is None else _source_from_row(row)

    def list_sources(self, *, limit: int, offset: int) -> list[Source]:
        statement = (
            sa.select(sources)
            .order_by(sources.c.created_at, sources.c.id)
            .limit(limit)
            .offset(offset)
        )
        with self._engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [_source_from_row(row) for row in rows]

    def save(self, source: Source, *, expected_version: int) -> Source:
        values = _source_values(source)
        values.pop("id")
        values.pop("created_at")
        statement = (
            sources.update()
            .where(sources.c.id == source.id, sources.c.version == expected_version)
            .values(**values)
            .returning(*sources.c)
        )
        with self._engine.begin() as connection:
            row = connection.execute(statement).mappings().one_or_none()
        if row is None:
            raise SourceConflictError("source version changed before update")
        return _source_from_row(row)

    def due(self, *, at: datetime, limit: int) -> list[Source]:
        due_at = sources.c.last_discovered_at + sources.c.crawl_interval_minutes * sa.text(
            "INTERVAL '1 minute'"
        )
        statement = (
            sa.select(sources)
            .where(
                sources.c.enabled.is_(True),
                sa.or_(sources.c.last_discovered_at.is_(None), due_at <= at),
            )
            .order_by(sources.c.last_discovered_at.asc().nullsfirst(), sources.c.id)
            .limit(limit)
        )
        with self._engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [_source_from_row(row) for row in rows]


class PostgresCrawlBatchRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def open(self, batch: CrawlBatch) -> CrawlBatch:
        statement = (
            insert(crawl_batches)
            .values(**_batch_values(batch))
            .on_conflict_do_nothing(constraint="uq_crawl_batches_idempotency_key")
            .returning(*crawl_batches.c)
        )
        with self._engine.begin() as connection:
            row = connection.execute(statement).mappings().one_or_none()
            if row is None:
                row = (
                    connection.execute(
                        sa.select(crawl_batches).where(
                            crawl_batches.c.idempotency_key == batch.idempotency_key
                        )
                    )
                    .mappings()
                    .one()
                )
        return _batch_from_row(row)

    def get(self, batch_id: UUID) -> CrawlBatch | None:
        statement = sa.select(crawl_batches).where(crawl_batches.c.id == batch_id)
        with self._engine.connect() as connection:
            row = connection.execute(statement).mappings().one_or_none()
        return None if row is None else _batch_from_row(row)

    def save(self, batch: CrawlBatch) -> CrawlBatch:
        values = _batch_values(batch)
        values.pop("id")
        values.pop("source_id")
        values.pop("idempotency_key")
        values.pop("window_started_at")
        values.pop("started_at")
        statement = (
            crawl_batches.update()
            .where(crawl_batches.c.id == batch.id)
            .values(**values)
            .returning(*crawl_batches.c)
        )
        with self._engine.begin() as connection:
            row = connection.execute(statement).mappings().one_or_none()
        if row is None:
            raise SourceConflictError("crawl batch disappeared before update")
        return _batch_from_row(row)
