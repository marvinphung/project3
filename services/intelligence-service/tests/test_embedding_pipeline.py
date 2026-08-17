from __future__ import annotations

import asyncio
import math
import threading
import time
from datetime import UTC, datetime
from uuid import UUID

import pytest
from footballpulse_intelligence_service.adapters.embedding_models import MockEmbeddingAdapter
from footballpulse_intelligence_service.application.embedding_pipeline import (
    EmbeddingPipeline,
    EmbeddingWorker,
    EmbeddingWorkStatus,
)
from footballpulse_intelligence_service.domain.embedding import EmbeddingInput, EmbeddingRecord

ARTICLE_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3ca101")
NOW = datetime(2026, 8, 10, 10, 0, tzinfo=UTC)


class RecordingRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, EmbeddingRecord] = {}

    def add_once(self, record: EmbeddingRecord) -> EmbeddingRecord:
        return self.items.setdefault(record.id, record)


def _input(article_id: UUID = ARTICLE_ID) -> EmbeddingInput:
    return EmbeddingInput(
        article_id,
        "Arsenal submit an offer",
        ("Vinícius Júnior", "Arsenal", "Real Madrid"),
        "Arsenal have submitted an offer to Real Madrid for Vinicius Junior.",
    )


def test_pipeline_persists_versioned_embedding_idempotently() -> None:
    repository = RecordingRepository()
    pipeline = EmbeddingPipeline(
        embedder=MockEmbeddingAdapter(),
        repository=repository,
        clock=lambda: NOW,
    )

    first = pipeline.process_batch([_input()])
    replay = pipeline.process_batch([_input()])

    assert first == replay
    assert len(repository.items) == 1
    record = first[0]
    assert record.article_version_id == ARTICLE_ID
    assert record.model_version == "fixture-v1"
    assert record.dimensions == 384
    assert math.isclose(sum(value * value for value in record.vector.values), 1.0)


class ConcurrencyPipeline:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()

    def process_batch(self, items: list[EmbeddingInput]) -> tuple[EmbeddingRecord, ...]:
        if self.fail:
            raise RuntimeError("embedding model unavailable")
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        time.sleep(0.02)
        with self.lock:
            self.active -= 1
        return ()


@pytest.mark.asyncio
async def test_worker_bounds_cpu_concurrency_and_reports_failure() -> None:
    pipeline = ConcurrencyPipeline()
    worker = EmbeddingWorker(pipeline, max_concurrency=1)

    results = await asyncio.gather(*(worker.run([_input()]) for _ in range(3)))

    assert all(result.status is EmbeddingWorkStatus.COMPLETED for result in results)
    assert pipeline.max_active == 1

    failed = await EmbeddingWorker(
        ConcurrencyPipeline(fail=True),
        clock=lambda: NOW,
    ).run([_input()])
    assert failed.status is EmbeddingWorkStatus.EMBEDDING_FAILED
    assert failed.records is None
    assert failed.error_type == "RuntimeError"
    assert failed.failed_at == NOW
