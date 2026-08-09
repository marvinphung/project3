from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from footballpulse_crawler_service.domain.errors import DomainValidationError


class CrawlBatchStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class CrawlBatch:
    id: UUID
    source_id: UUID
    idempotency_key: str
    window_started_at: datetime
    status: CrawlBatchStatus
    discovered_count: int
    fetched_count: int
    failed_count: int
    started_at: datetime
    completed_at: datetime | None

    def complete(
        self,
        *,
        status: CrawlBatchStatus,
        discovered_count: int,
        fetched_count: int,
        failed_count: int,
        completed_at: datetime,
    ) -> CrawlBatch:
        if status not in {
            CrawlBatchStatus.COMPLETED,
            CrawlBatchStatus.PARTIAL,
            CrawlBatchStatus.FAILED,
        }:
            raise DomainValidationError("completed batch requires a terminal status")
        if min(discovered_count, fetched_count, failed_count) < 0:
            raise DomainValidationError("crawl batch counts cannot be negative")
        if fetched_count + failed_count > discovered_count:
            raise DomainValidationError("fetched and failed counts cannot exceed discovered count")
        return replace(
            self,
            status=status,
            discovered_count=discovered_count,
            fetched_count=fetched_count,
            failed_count=failed_count,
            completed_at=completed_at,
        )
