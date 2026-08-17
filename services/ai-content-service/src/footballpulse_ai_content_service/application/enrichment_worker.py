from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from footballpulse_ai_content_service.contracts.batch import (
    BatchRecord,
    FailedBatchRecord,
)
from footballpulse_ai_content_service.contracts.enrichment import ArticleEnrichmentInput


class EnrichmentQueue(Protocol):
    def claim_pending(self, *, limit: int) -> tuple[ArticleEnrichmentInput, ...]: ...

    def save_records(self, records: tuple[BatchRecord, ...], *, processed_at: datetime) -> None: ...


class EnrichmentService(Protocol):
    def enrich(self, inputs: tuple[ArticleEnrichmentInput, ...]) -> tuple[BatchRecord, ...]: ...


@dataclass(frozen=True, slots=True)
class EnrichmentWorkerReport:
    claimed: int
    succeeded: int
    failed: int


class EnrichmentWorker:
    def __init__(
        self,
        *,
        queue: EnrichmentQueue,
        service: EnrichmentService,
        clock: Callable[[], datetime],
    ) -> None:
        self._queue = queue
        self._service = service
        self._clock = clock

    def run_once(self, *, limit: int = 10) -> EnrichmentWorkerReport:
        if not 1 <= limit <= 100:
            raise ValueError("enrichment worker limit must be between 1 and 100")
        inputs = self._queue.claim_pending(limit=limit)
        if not inputs:
            return EnrichmentWorkerReport(0, 0, 0)
        try:
            records = self._service.enrich(inputs)
        except Exception as error:
            records = tuple(
                FailedBatchRecord(
                    article_version_id=source.article_version_id,
                    input_hash=source.input_hash,
                    status="ERROR",
                    error_code="WORKER_RUNTIME_ERROR",
                    error=type(error).__name__,
                )
                for source in inputs
            )
        self._queue.save_records(records, processed_at=self._clock())
        failed = sum(isinstance(record, FailedBatchRecord) for record in records)
        return EnrichmentWorkerReport(len(inputs), len(records) - failed, failed)
