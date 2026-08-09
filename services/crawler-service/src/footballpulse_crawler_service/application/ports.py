from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from footballpulse_crawler_service.domain.crawl_batch import CrawlBatch
from footballpulse_crawler_service.domain.source import Source


class SourceRepository(Protocol):
    def add(self, source: Source) -> Source: ...

    def get(self, source_id: UUID) -> Source | None: ...

    def list_sources(self, *, limit: int, offset: int) -> list[Source]: ...

    def save(self, source: Source, *, expected_version: int) -> Source: ...

    def due(self, *, at: datetime, limit: int) -> list[Source]: ...


class CrawlBatchRepository(Protocol):
    def open(self, batch: CrawlBatch) -> CrawlBatch: ...

    def save(self, batch: CrawlBatch) -> CrawlBatch: ...

    def get(self, batch_id: UUID) -> CrawlBatch | None: ...
