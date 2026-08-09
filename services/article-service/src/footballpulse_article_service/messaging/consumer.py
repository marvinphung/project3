from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from confluent_kafka import Consumer
from footballpulse_event_contracts.article import ArticleDiscoveredEvent

ARTICLE_DISCOVERED_TOPIC = "article.discovered.v1"


class ArticleHandler(Protocol):
    def handle(self, event: ArticleDiscoveredEvent) -> object: ...


class ConsumerMessage(Protocol):
    def value(self) -> bytes | None: ...

    def error(self) -> object | None: ...


class ManualConsumer(Protocol):
    def subscribe(self, topics: Sequence[str]) -> None: ...

    def poll(self, timeout: float) -> ConsumerMessage | None: ...

    def commit(
        self,
        *,
        message: ConsumerMessage,
        asynchronous: bool,
    ) -> object: ...

    def close(self) -> None: ...


def consumer_config(*, bootstrap_servers: str, group_id: str) -> dict[str, object]:
    if not bootstrap_servers.strip() or not group_id.strip():
        raise ValueError("Kafka bootstrap servers and group ID are required")
    # Manual synchronous commit pattern:
    # https://docs.confluent.io/kafka-clients/python/current/overview.html
    return {
        "bootstrap.servers": bootstrap_servers,
        "group.id": group_id,
        "enable.auto.commit": False,
        "enable.auto.offset.store": False,
        "auto.offset.reset": "earliest",
    }


def create_consumer(*, bootstrap_servers: str, group_id: str) -> Consumer:
    return Consumer(consumer_config(bootstrap_servers=bootstrap_servers, group_id=group_id))


class ArticleDiscoveredRecordHandler:
    def __init__(self, *, service: ArticleHandler) -> None:
        self._service = service

    def handle(self, payload: bytes) -> object:
        event = ArticleDiscoveredEvent.model_validate_json(payload)
        return self._service.handle(event)


class ConfluentArticleWorker:
    def __init__(
        self,
        *,
        consumer: ManualConsumer,
        handler: ArticleDiscoveredRecordHandler,
    ) -> None:
        self._consumer = consumer
        self._handler = handler
        self._consumer.subscribe([ARTICLE_DISCOVERED_TOPIC])

    def run_once(self, *, timeout_seconds: float = 1.0) -> object | None:
        if timeout_seconds < 0:
            raise ValueError("poll timeout must not be negative")
        message = self._consumer.poll(timeout_seconds)
        if message is None:
            return None
        error = message.error()
        if error is not None:
            raise RuntimeError(f"Kafka consumer error: {error}")
        payload = message.value()
        if payload is None:
            raise ValueError("Kafka article event payload must not be null")
        result = self._handler.handle(payload)
        # The documented message commit stores offset + 1. Synchronous mode makes
        # commit failure observable instead of reporting success early.
        self._consumer.commit(message=message, asynchronous=False)
        return result

    def close(self) -> None:
        self._consumer.close()
