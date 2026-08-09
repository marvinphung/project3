from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import pytest
from footballpulse_article_service.messaging.outbox import (
    ConfluentKafkaPublisher,
    KafkaPublishError,
    OutboxPublisher,
    OutboxRecord,
    PublishBatchResult,
)

NOW = datetime(2026, 8, 1, 0, 5, tzinfo=UTC)


class FakeOutboxRepository:
    def __init__(self, records: list[OutboxRecord]) -> None:
        self.records = records
        self.requested_limits: list[int] = []
        self.published: list[UUID] = []
        self.failed: list[UUID] = []

    def list_pending_outbox(self, *, limit: int, now: datetime) -> list[OutboxRecord]:
        assert now == NOW
        self.requested_limits.append(limit)
        return self.records[:limit]

    def mark_outbox_published(self, event_id: UUID, *, published_at: datetime) -> None:
        assert published_at == NOW
        self.published.append(event_id)

    def record_outbox_failure(self, event_id: UUID, *, failed_at: datetime) -> None:
        assert failed_at == NOW
        self.failed.append(event_id)


@dataclass
class FakeKafkaPublisher:
    failing_event_id: UUID | None = None

    def __post_init__(self) -> None:
        self.sent: list[tuple[str, str, bytes]] = []

    def publish(self, *, topic: str, key: str, value: bytes) -> None:
        if self.failing_event_id is not None and str(self.failing_event_id).encode() in value:
            raise KafkaPublishError("Kafka unavailable")
        self.sent.append((topic, key, value))


def _record(index: int) -> OutboxRecord:
    event_id = UUID(f"018f8b45-b634-7c81-a47d-9a7c2f3c43{index:02d}")
    return OutboxRecord(
        event_id=event_id,
        topic="article.cleaned.v1",
        key="article-1",
        event={"event_id": str(event_id), "event_type": "article.cleaned"},
    )


def test_publishes_bounded_batch_then_marks_each_event() -> None:
    repository = FakeOutboxRepository([_record(1), _record(2), _record(3)])
    kafka = FakeKafkaPublisher()
    publisher = OutboxPublisher(repository=repository, kafka=kafka, clock=lambda: NOW)

    result = publisher.publish_pending(limit=2)

    assert result == PublishBatchResult(attempted=2, published=2, failed=0)
    assert repository.requested_limits == [2]
    assert repository.published == [_record(1).event_id, _record(2).event_id]
    assert len(kafka.sent) == 2


def test_failed_delivery_is_recorded_and_not_marked_published() -> None:
    failing = _record(2)
    repository = FakeOutboxRepository([_record(1), failing])
    kafka = FakeKafkaPublisher(failing_event_id=failing.event_id)
    publisher = OutboxPublisher(repository=repository, kafka=kafka, clock=lambda: NOW)

    result = publisher.publish_pending(limit=10)

    assert result == PublishBatchResult(attempted=2, published=1, failed=1)
    assert repository.published == [_record(1).event_id]
    assert repository.failed == [failing.event_id]


def test_confluent_adapter_waits_for_delivery_report() -> None:
    class FakeProducer:
        def __init__(self) -> None:
            self.callback: Callable[[object | None, object], None] | None = None

        def produce(
            self,
            topic: str,
            *,
            key: bytes,
            value: bytes,
            on_delivery: Callable[[object | None, object], None],
        ) -> None:
            assert topic == "article.cleaned.v1"
            assert key == b"article-1"
            assert value == b"payload"
            self.callback = on_delivery

        def flush(self, timeout: float) -> int:
            assert timeout == 5.0
            assert self.callback is not None
            self.callback(None, object())
            return 0

    ConfluentKafkaPublisher(producer=FakeProducer()).publish(
        topic="article.cleaned.v1",
        key="article-1",
        value=b"payload",
    )


def test_confluent_adapter_surfaces_delivery_failure() -> None:
    class FakeProducer:
        def __init__(self) -> None:
            self.callback: Callable[[object | None, object], None] | None = None

        def produce(
            self,
            topic: str,
            *,
            key: bytes,
            value: bytes,
            on_delivery: Callable[[object | None, object], None],
        ) -> None:
            del topic, key, value
            self.callback = on_delivery

        def flush(self, timeout: float) -> int:
            del timeout
            assert self.callback is not None
            self.callback("broker unavailable", object())
            return 0

    with pytest.raises(KafkaPublishError, match="broker unavailable"):
        ConfluentKafkaPublisher(producer=FakeProducer()).publish(
            topic="article.cleaned.v1",
            key="article-1",
            value=b"payload",
        )
