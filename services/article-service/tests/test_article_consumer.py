from __future__ import annotations

import json
from pathlib import Path

import pytest
from footballpulse_article_service.messaging.consumer import (
    ARTICLE_DISCOVERED_TOPIC,
    ArticleDiscoveredRecordHandler,
    ConfluentArticleWorker,
    consumer_config,
)
from footballpulse_event_contracts.article import ArticleDiscoveredEvent

EVENT_FIXTURE = (
    Path(__file__).parents[3]
    / "tests"
    / "contract"
    / "fixtures"
    / "article_discovered_v1.valid.json"
)


class FakeMessage:
    def __init__(self, value: bytes, *, error: object | None = None) -> None:
        self._value = value
        self._error = error

    def value(self) -> bytes:
        return self._value

    def error(self) -> object | None:
        return self._error


class FakeConsumer:
    def __init__(self, message: FakeMessage, *, fail_first_commit: bool = False) -> None:
        self.message = message
        self.fail_first_commit = fail_first_commit
        self.commits = 0
        self.subscriptions: list[list[str]] = []

    def subscribe(self, topics: list[str]) -> None:
        self.subscriptions.append(topics)

    def poll(self, timeout: float) -> FakeMessage:
        del timeout
        return self.message

    def commit(self, *, message: FakeMessage, asynchronous: bool) -> None:
        assert message is self.message
        assert asynchronous is False
        self.commits += 1
        if self.fail_first_commit and self.commits == 1:
            raise RuntimeError("commit interrupted")

    def close(self) -> None:
        return None


class FakeService:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

    def handle(self, event: ArticleDiscoveredEvent) -> object:
        self.calls += 1
        if self.fail:
            raise RuntimeError("MongoDB unavailable")
        return event.event_id


def test_consumer_configuration_disables_automatic_offset_progress() -> None:
    config = consumer_config(bootstrap_servers="localhost:9092", group_id="article-service")

    assert config["enable.auto.commit"] is False
    assert config["enable.auto.offset.store"] is False
    assert config["auto.offset.reset"] == "earliest"


def test_commits_message_synchronously_only_after_handler_success() -> None:
    service = FakeService()
    handler = ArticleDiscoveredRecordHandler(service=service)
    consumer = FakeConsumer(FakeMessage(EVENT_FIXTURE.read_bytes()))
    worker = ConfluentArticleWorker(consumer=consumer, handler=handler)

    result = worker.run_once(timeout_seconds=0.01)

    assert result is not None
    assert service.calls == 1
    assert consumer.commits == 1
    assert consumer.subscriptions == [[ARTICLE_DISCOVERED_TOPIC]]


def test_does_not_commit_when_durable_handler_fails() -> None:
    service = FakeService(fail=True)
    consumer = FakeConsumer(FakeMessage(EVENT_FIXTURE.read_bytes()))
    worker = ConfluentArticleWorker(
        consumer=consumer,
        handler=ArticleDiscoveredRecordHandler(service=service),
    )

    with pytest.raises(RuntimeError, match="MongoDB"):
        worker.run_once(timeout_seconds=0.01)

    assert consumer.commits == 0


def test_redelivery_can_commit_after_crash_between_durable_write_and_offset_commit() -> None:
    service = FakeService()
    consumer = FakeConsumer(
        FakeMessage(EVENT_FIXTURE.read_bytes()),
        fail_first_commit=True,
    )
    worker = ConfluentArticleWorker(
        consumer=consumer,
        handler=ArticleDiscoveredRecordHandler(service=service),
    )

    with pytest.raises(RuntimeError, match="commit interrupted"):
        worker.run_once(timeout_seconds=0.01)
    worker.run_once(timeout_seconds=0.01)

    assert service.calls == 2
    assert consumer.commits == 2


def test_invalid_event_is_rejected_before_commit() -> None:
    invalid = json.loads(EVENT_FIXTURE.read_text())
    invalid["payload"]["canonical_url"] = "file:///etc/passwd"
    consumer = FakeConsumer(FakeMessage(json.dumps(invalid).encode()))
    worker = ConfluentArticleWorker(
        consumer=consumer,
        handler=ArticleDiscoveredRecordHandler(service=FakeService()),
    )

    with pytest.raises(ValueError):
        worker.run_once(timeout_seconds=0.01)

    assert consumer.commits == 0
