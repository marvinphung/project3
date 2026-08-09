from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from confluent_kafka import Producer


@dataclass(frozen=True, slots=True)
class OutboxRecord:
    event_id: UUID
    topic: str
    key: str
    event: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class PublishBatchResult:
    attempted: int
    published: int
    failed: int


class OutboxRepository(Protocol):
    def list_pending_outbox(self, *, limit: int, now: datetime) -> list[OutboxRecord]: ...

    def mark_outbox_published(self, event_id: UUID, *, published_at: datetime) -> None: ...

    def record_outbox_failure(self, event_id: UUID, *, failed_at: datetime) -> None: ...


class KafkaPublisher(Protocol):
    def publish(self, *, topic: str, key: str, value: bytes) -> None: ...


class KafkaPublishError(RuntimeError):
    """Raised when Kafka did not acknowledge an outbox record."""


class ProducerClient(Protocol):
    def produce(
        self,
        topic: str,
        *,
        key: bytes,
        value: bytes,
        on_delivery: Callable[[object | None, object], None],
    ) -> None: ...

    def flush(self, timeout: float) -> int: ...


def create_producer(*, bootstrap_servers: str) -> Producer:
    if not bootstrap_servers.strip():
        raise ValueError("Kafka bootstrap servers are required")
    return Producer({"bootstrap.servers": bootstrap_servers})


class ConfluentKafkaPublisher:
    def __init__(self, *, producer: ProducerClient, delivery_timeout_seconds: float = 5.0) -> None:
        if delivery_timeout_seconds <= 0:
            raise ValueError("Kafka delivery timeout must be positive")
        self._producer = producer
        self._delivery_timeout = delivery_timeout_seconds

    def publish(self, *, topic: str, key: str, value: bytes) -> None:
        delivery_errors: list[object] = []
        delivered = False

        def on_delivery(error: object | None, message: object) -> None:
            nonlocal delivered
            del message
            delivered = True
            if error is not None:
                delivery_errors.append(error)

        # Delivery callbacks are served by poll/flush. Blocking flush keeps the
        # outbox status PENDING until Kafka reports the record outcome.
        try:
            self._producer.produce(
                topic,
                key=key.encode("utf-8"),
                value=value,
                on_delivery=on_delivery,
            )
            remaining = self._producer.flush(self._delivery_timeout)
        except Exception as exc:
            raise KafkaPublishError("Kafka producer call failed") from exc
        if remaining or not delivered:
            raise KafkaPublishError("Kafka delivery did not complete before timeout")
        if delivery_errors:
            raise KafkaPublishError(f"Kafka delivery failed: {delivery_errors[0]}")


class OutboxPublisher:
    def __init__(
        self,
        *,
        repository: OutboxRepository,
        kafka: KafkaPublisher,
        clock: Callable[[], datetime],
    ) -> None:
        self._repository = repository
        self._kafka = kafka
        self._clock = clock

    def publish_pending(self, *, limit: int = 50) -> PublishBatchResult:
        if not 1 <= limit <= 100:
            raise ValueError("outbox publish limit must be between 1 and 100")
        now = self._clock()
        records = self._repository.list_pending_outbox(limit=limit, now=now)
        published = 0
        failed = 0
        for record in records:
            payload = json.dumps(
                record.event,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            try:
                self._kafka.publish(topic=record.topic, key=record.key, value=payload)
            except KafkaPublishError:
                self._repository.record_outbox_failure(record.event_id, failed_at=now)
                failed += 1
                continue
            self._repository.mark_outbox_published(record.event_id, published_at=now)
            published += 1
        return PublishBatchResult(len(records), published, failed)
