from __future__ import annotations

import asyncio
import threading
import time
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from footballpulse_intelligence_service.application.entity_extraction import (
    EntityExtractionResult,
    ExtractionRequest,
)
from footballpulse_intelligence_service.application.entity_worker import (
    EntityExtractionWorker,
    EntityWorkStatus,
)


class ConcurrencyRecordingPipeline:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()

    def process(self, request: ExtractionRequest) -> EntityExtractionResult:
        if self.fail:
            raise RuntimeError("model unavailable")
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        time.sleep(0.02)
        with self.lock:
            self.active -= 1
        return EntityExtractionResult(
            request.article_version_id,
            (),
            "mock-gliner",
            "fixture-v1",
            0.5,
            0.75,
        )


def _request() -> ExtractionRequest:
    return ExtractionRequest(uuid4(), "Title", "Article content")


@pytest.mark.asyncio
async def test_worker_enforces_cpu_concurrency_limit() -> None:
    pipeline = ConcurrencyRecordingPipeline()
    worker = EntityExtractionWorker(pipeline, max_concurrency=1)

    results = await asyncio.gather(*(worker.run(_request()) for _ in range(3)))

    assert all(result.status is EntityWorkStatus.COMPLETED for result in results)
    assert pipeline.max_active == 1


@pytest.mark.asyncio
async def test_worker_returns_explicit_failure_without_mock_fallback() -> None:
    pipeline = ConcurrencyRecordingPipeline(fail=True)
    worker = EntityExtractionWorker(
        pipeline,
        max_concurrency=1,
        clock=lambda: datetime(2026, 8, 10, 9, 0, tzinfo=UTC),
    )

    result = await worker.run(_request())

    assert result.status is EntityWorkStatus.ENTITY_EXTRACTION_FAILED
    assert result.extraction is None
    assert result.error_type == "RuntimeError"
