from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import UUID, uuid4

from footballpulse_crawler_service.application.ports import (
    CrawlBatchRepository,
    SourceRepository,
)
from footballpulse_crawler_service.domain.crawl_batch import CrawlBatch, CrawlBatchStatus
from footballpulse_crawler_service.domain.errors import (
    DomainValidationError,
    SourceConflictError,
    SourceNotFoundError,
)
from footballpulse_crawler_service.domain.source import NewSource, Source


class SourceService:
    def __init__(
        self,
        repository: SourceRepository,
        *,
        clock: Callable[[], datetime],
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._id_factory = id_factory

    def create(self, configuration: NewSource) -> Source:
        now = self._clock()
        return self._repository.add(
            Source(
                id=self._id_factory(),
                name=configuration.name,
                rss_url=configuration.rss_url,
                allowed_domains=configuration.allowed_domains,
                source_type=configuration.source_type,
                reliability_tier=configuration.reliability_tier,
                enabled=True,
                crawl_interval_minutes=configuration.crawl_interval_minutes,
                max_concurrency=configuration.max_concurrency,
                last_discovered_at=None,
                created_at=now,
                updated_at=now,
                version=1,
            )
        )

    def get(self, source_id: UUID) -> Source:
        source = self._repository.get(source_id)
        if source is None:
            raise SourceNotFoundError(f"source {source_id} was not found")
        return source

    def list_sources(self, *, limit: int = 100, offset: int = 0) -> list[Source]:
        if not 1 <= limit <= 200 or offset < 0:
            raise DomainValidationError("source pagination is outside allowed bounds")
        return self._repository.list_sources(limit=limit, offset=offset)

    def update(
        self,
        source_id: UUID,
        configuration: NewSource,
        *,
        expected_version: int,
    ) -> Source:
        source = self.get(source_id)
        self._check_version(source, expected_version)
        updated = source.with_configuration(configuration, now=self._clock())
        return self._repository.save(updated, expected_version=expected_version)

    def toggle(self, source_id: UUID, *, enabled: bool, expected_version: int) -> Source:
        source = self.get(source_id)
        self._check_version(source, expected_version)
        updated = source.with_enabled(enabled, now=self._clock())
        if updated is source:
            return source
        return self._repository.save(updated, expected_version=expected_version)

    def due(self, *, at: datetime, limit: int = 100) -> list[Source]:
        if not 1 <= limit <= 200:
            raise DomainValidationError("due-source limit is outside allowed bounds")
        return self._repository.due(at=at, limit=limit)

    @staticmethod
    def _check_version(source: Source, expected_version: int) -> None:
        if source.version != expected_version:
            raise SourceConflictError(
                f"source version conflict: expected {expected_version}, current {source.version}"
            )


class CrawlBatchService:
    def __init__(
        self,
        source_repository: SourceRepository,
        batch_repository: CrawlBatchRepository,
        *,
        clock: Callable[[], datetime],
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._source_repository = source_repository
        self._batch_repository = batch_repository
        self._clock = clock
        self._id_factory = id_factory

    def open(
        self, *, source_id: UUID, idempotency_key: str, window_started_at: datetime
    ) -> CrawlBatch:
        source = self._source_repository.get(source_id)
        if source is None:
            raise SourceNotFoundError(f"source {source_id} was not found")
        if not source.enabled:
            raise SourceConflictError("disabled source cannot start a crawl batch")
        normalized_key = idempotency_key.strip()
        if not normalized_key or len(normalized_key) > 256:
            raise DomainValidationError("idempotency key must contain 1 to 256 characters")
        return self._batch_repository.open(
            CrawlBatch(
                id=self._id_factory(),
                source_id=source_id,
                idempotency_key=normalized_key,
                window_started_at=window_started_at,
                status=CrawlBatchStatus.RUNNING,
                discovered_count=0,
                fetched_count=0,
                failed_count=0,
                started_at=self._clock(),
                completed_at=None,
            )
        )

    def complete(
        self,
        batch_id: UUID,
        *,
        status: CrawlBatchStatus,
        discovered_count: int,
        fetched_count: int,
        failed_count: int,
    ) -> CrawlBatch:
        batch = self._batch_repository.get(batch_id)
        if batch is None:
            raise SourceNotFoundError(f"crawl batch {batch_id} was not found")
        completed = batch.complete(
            status=status,
            discovered_count=discovered_count,
            fetched_count=fetched_count,
            failed_count=failed_count,
            completed_at=self._clock(),
        )
        return self._batch_repository.save(completed)

    def get(self, batch_id: UUID) -> CrawlBatch:
        batch = self._batch_repository.get(batch_id)
        if batch is None:
            raise SourceNotFoundError(f"crawl batch {batch_id} was not found")
        return batch
