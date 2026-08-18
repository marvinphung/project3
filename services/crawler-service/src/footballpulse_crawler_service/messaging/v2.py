from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from confluent_kafka import Producer
from footballpulse_event_contracts import NewsCrawledEvent, NewsCrawledPayload

NEWS_CRAWLED_TOPIC = "news.crawled.v1"


class V2NewsCrawledPublisher:
    def __init__(self, producer: Producer, *, source_name: str) -> None:
        if not source_name.strip():
            raise ValueError("source name is required")
        self._producer = producer
        self._source_name = source_name

    def publish(self, *, article_id: UUID, canonical_url: str) -> None:
        event = NewsCrawledEvent(
            event_id=uuid4(),
            event_type="news.crawled",
            event_version=1,
            occurred_at=datetime.now(UTC),
            producer="crawler-service",
            correlation_id=article_id,
            causation_id=None,
            aggregate_type="news_article",
            aggregate_id=article_id,
            idempotency_key=str(article_id),
            payload=NewsCrawledPayload(
                article_id=article_id,
                canonical_url=canonical_url,
                source_name=self._source_name,
                published_time=None,
            ),
        )
        self._producer.produce(
            NEWS_CRAWLED_TOPIC,
            key=str(article_id).encode("ascii"),
            value=json.dumps(event.model_dump(mode="json"), separators=(",", ":")).encode(),
        )
        self._producer.flush(10)
