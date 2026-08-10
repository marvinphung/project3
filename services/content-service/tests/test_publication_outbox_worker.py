from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from footballpulse_content_service.editorial.publication_outbox import (
    PublicationPublishedEvent,
)
from footballpulse_content_service.editorial.publication_outbox_worker import (
    PublicationOutboxWorker,
    PublicationPublishError,
    PublishBatchResult,
)

NOW = datetime(2026, 8, 10, 12, tzinfo=UTC)


def event(index: int) -> PublicationPublishedEvent:
    event_id = UUID(int=index)
    return PublicationPublishedEvent(
        event_id=event_id,
        topic="publication.published.v1",
        key="article-1",
        occurred_at=NOW,
        payload={"event_id": str(event_id), "title_vi": "Arsenal hỏi mua"},
    )


class FakeRepository:
    def __init__(self, events: list[PublicationPublishedEvent]) -> None:
        self.events = events
        self.published: list[UUID] = []
        self.failed: list[UUID] = []

    def list_pending(self, *, limit: int, now: datetime) -> list[PublicationPublishedEvent]:
        assert now == NOW
        return self.events[:limit]

    def mark_published(self, event_id: UUID, *, published_at: datetime) -> None:
        assert published_at == NOW
        self.published.append(event_id)

    def record_failure(self, event_id: UUID, *, failed_at: datetime, error: str) -> None:
        assert failed_at == NOW
        assert error
        self.failed.append(event_id)


class FakePublisher:
    def __init__(self, failing: UUID | None = None) -> None:
        self.failing = failing
        self.sent: list[PublicationPublishedEvent] = []

    def publish(self, event: PublicationPublishedEvent) -> None:
        if event.event_id == self.failing:
            raise PublicationPublishError("broker unavailable")
        self.sent.append(event)


def test_worker_publishes_bounded_batch_and_marks_success() -> None:
    repository = FakeRepository([event(1), event(2), event(3)])
    publisher = FakePublisher()
    worker = PublicationOutboxWorker(repository=repository, publisher=publisher, clock=lambda: NOW)

    result = worker.publish_pending(limit=2)

    assert result == PublishBatchResult(attempted=2, published=2, failed=0)
    assert repository.published == [UUID(int=1), UUID(int=2)]
    assert repository.failed == []


def test_worker_records_failure_and_continues_batch() -> None:
    repository = FakeRepository([event(1), event(2)])
    publisher = FakePublisher(failing=UUID(int=2))
    worker = PublicationOutboxWorker(repository=repository, publisher=publisher, clock=lambda: NOW)

    result = worker.publish_pending(limit=10)

    assert result == PublishBatchResult(attempted=2, published=1, failed=1)
    assert repository.published == [UUID(int=1)]
    assert repository.failed == [UUID(int=2)]
