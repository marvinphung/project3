from __future__ import annotations

import json
from collections.abc import Callable
from typing import Protocol

from footballpulse_content_service.editorial.publication_outbox import PublicationPublishedEvent
from footballpulse_content_service.editorial.publication_outbox_worker import (
    PublicationPublishError,
)


class InMemoryPublicationPublisher:
    """Deterministic publisher for local development and integration demos."""

    def __init__(self) -> None:
        self.events: list[PublicationPublishedEvent] = []

    def publish(self, event: PublicationPublishedEvent) -> None:
        self.events.append(event)


class JsonPublicationPublisher:
    """Serialize an event before handing it to Kafka, HTTP, or another transport."""

    def __init__(self, *, send: Callable[[str, str, bytes], object]) -> None:
        self._send = send

    def publish(self, event: PublicationPublishedEvent) -> None:
        payload = json.dumps(
            event.payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        try:
            self._send(event.topic, event.key, payload)
        except Exception as error:
            raise PublicationPublishError("publication event transport failed") from error


class KafkaProducer(Protocol):
    def produce(
        self,
        topic: str,
        *,
        key: bytes,
        value: bytes,
        on_delivery: Callable[[object | None, object], None],
    ) -> None: ...

    def flush(self, timeout: float) -> int: ...


class KafkaPublicationPublisher:
    def __init__(self, *, producer: KafkaProducer, delivery_timeout_seconds: float = 5.0) -> None:
        if delivery_timeout_seconds <= 0:
            raise ValueError("Kafka delivery timeout must be positive")
        self._producer = producer
        self._delivery_timeout = delivery_timeout_seconds

    def publish(self, event: PublicationPublishedEvent) -> None:
        payload = json.dumps(
            event.payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        delivered = False
        delivery_errors: list[object] = []

        def on_delivery(error: object | None, message: object) -> None:
            nonlocal delivered
            del message
            delivered = True
            if error is not None:
                delivery_errors.append(error)

        try:
            self._producer.produce(
                event.topic,
                key=event.key.encode("utf-8"),
                value=payload,
                on_delivery=on_delivery,
            )
            remaining = self._producer.flush(self._delivery_timeout)
        except Exception as error:
            raise PublicationPublishError("publication Kafka publish failed") from error
        if remaining or not delivered:
            raise PublicationPublishError("publication Kafka delivery timed out")
        if delivery_errors:
            raise PublicationPublishError(
                f"publication Kafka delivery failed: {delivery_errors[0]}"
            )
