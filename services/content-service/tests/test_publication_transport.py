from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from footballpulse_content_service.editorial.publication_outbox import PublicationPublishedEvent
from footballpulse_content_service.editorial.publication_outbox_worker import (
    PublicationPublishError,
)
from footballpulse_content_service.editorial.publication_transport import (
    InMemoryPublicationPublisher,
    JsonPublicationPublisher,
    KafkaPublicationPublisher,
)

NOW = datetime(2026, 8, 10, 12, tzinfo=UTC)


def event() -> PublicationPublishedEvent:
    return PublicationPublishedEvent(
        event_id=UUID(int=1),
        topic="publication.published.v1",
        key="article-1",
        occurred_at=NOW,
        payload={"event_id": "1", "title_vi": "Arsenal hỏi mua"},
    )


def test_in_memory_publisher_keeps_events_for_local_demo() -> None:
    publisher = InMemoryPublicationPublisher()

    publisher.publish(event())

    assert publisher.events == [event()]


def test_json_publisher_serializes_sorted_utf8_payload() -> None:
    sent: list[tuple[str, str, bytes]] = []
    publisher = JsonPublicationPublisher(
        send=lambda topic, key, value: sent.append((topic, key, value))
    )

    publisher.publish(event())

    assert sent == [
        (
            "publication.published.v1",
            "article-1",
            b'{"event_id":"1","title_vi":"Arsenal h\xe1\xbb\x8fi mua"}',
        )
    ]


def test_json_publisher_wraps_transport_errors() -> None:
    publisher = JsonPublicationPublisher(send=lambda *_: 1 / 0)

    try:
        publisher.publish(event())
    except PublicationPublishError as error:
        assert "transport" in str(error)
    else:
        raise AssertionError("expected PublicationPublishError")


def test_kafka_publisher_waits_for_delivery_callback() -> None:
    class FakeProducer:
        def __init__(self) -> None:
            self.callback: Callable[[object | None, object], None] | None = None

        def produce(self, topic, *, key, value, on_delivery):
            assert topic == "publication.published.v1"
            assert key == b"article-1"
            assert b"title_vi" in value
            self.callback = on_delivery

        def flush(self, timeout):
            assert timeout == 5.0
            assert self.callback is not None
            self.callback(None, object())
            return 0

    KafkaPublicationPublisher(producer=FakeProducer()).publish(event())


def test_kafka_publisher_surfaces_delivery_failure() -> None:
    class FakeProducer:
        def __init__(self) -> None:
            self.callback: Callable[[object | None, object], None] | None = None

        def produce(self, topic, *, key, value, on_delivery):
            del topic, key, value
            self.callback = on_delivery

        def flush(self, timeout):
            del timeout
            assert self.callback is not None
            self.callback("broker unavailable", object())
            return 0

    publisher = KafkaPublicationPublisher(producer=FakeProducer())
    try:
        publisher.publish(event())
    except PublicationPublishError as error:
        assert "delivery" in str(error)
    else:
        raise AssertionError("expected PublicationPublishError")
