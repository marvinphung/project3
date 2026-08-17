from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from footballpulse_ai_content_service.application.enrichment_worker import EnrichmentWorker
from footballpulse_ai_content_service.contracts.batch import (
    FailedBatchRecord,
    SuccessfulBatchRecord,
)
from footballpulse_ai_content_service.contracts.enrichment import (
    ArticleEnrichmentInput,
    ArticleEnrichmentOutput,
    EventType,
)

ARTICLE_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c3101")
NOW = datetime(2026, 8, 17, 12, tzinfo=UTC)


def article_input() -> ArticleEnrichmentInput:
    return ArticleEnrichmentInput.model_validate(
        {
            "contract_version": "article-enrichment.v1",
            "article_version_id": ARTICLE_ID,
            "input_hash": "a" * 64,
            "title": "Arsenal update",
            "cleaned_content": "Arsenal submitted an offer.",
            "published_at": NOW,
            "source_id": UUID(int=2),
            "source_reliability_tier": 2,
            "canonical_entities": [],
            "unresolved_mentions": [],
        }
    )


class Queue:
    def __init__(self) -> None:
        self.saved = []

    def claim_pending(self, *, limit: int):
        assert limit == 10
        return (article_input(),)

    def save_records(self, records, *, processed_at):
        self.saved.extend(records)
        assert processed_at == NOW


class SuccessfulService:
    def enrich(self, inputs):
        source = inputs[0]
        return (
            SuccessfulBatchRecord(
                article_version_id=source.article_version_id,
                status="SUCCESS",
                result=ArticleEnrichmentOutput(
                    contract_version="article-enrichment.v1",
                    article_version_id=source.article_version_id,
                    input_hash=source.input_hash,
                    event_type=EventType.OTHER,
                    summary_en=source.cleaned_content,
                    claims=(),
                    model_version="offline-v1",
                    prompt_version="offline-v1",
                ),
            ),
        )


def test_worker_persists_terminal_provider_records() -> None:
    queue = Queue()
    worker = EnrichmentWorker(
        queue=queue,
        service=SuccessfulService(),
        clock=lambda: NOW,
    )

    report = worker.run_once(limit=10)

    assert report.claimed == 1
    assert report.succeeded == 1
    assert report.failed == 0
    assert queue.saved[0].status == "SUCCESS"


def test_worker_contains_provider_failure_and_records_safe_error_type() -> None:
    queue = Queue()

    class BrokenService:
        def enrich(self, inputs):
            raise RuntimeError("secret provider response")

    worker = EnrichmentWorker(queue=queue, service=BrokenService(), clock=lambda: NOW)

    report = worker.run_once(limit=10)

    assert report.failed == 1
    assert isinstance(queue.saved[0], FailedBatchRecord)
    assert queue.saved[0].error_code == "WORKER_RUNTIME_ERROR"
    assert queue.saved[0].error == "RuntimeError"
