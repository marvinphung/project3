from __future__ import annotations

import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from confluent_kafka import Consumer
from footballpulse_event_contracts import NewsCrawledEvent
from pymongo.database import Database

NEWS_CRAWLED_TOPIC = "news.crawled.v1"

EntityPrediction = dict[str, Any]
EntityExtractor = Callable[[str], list[EntityPrediction]]
MongoDocument = dict[str, Any]


class V2EntityProcessor:
    """Processes article pointers concurrently and upserts one entity document."""

    def __init__(
        self,
        *,
        database: Database[MongoDocument],
        extractor: EntityExtractor,
        workers: int = 6,
    ) -> None:
        if workers < 1:
            raise ValueError("entity worker count must be positive")
        self._database = database
        self._extractor = extractor
        self._workers = workers

    def process_article(self, article_id: UUID) -> UUID:
        content = self._database.news_content.find_one({"_id": article_id})
        if content is None or not isinstance(content.get("content"), str):
            raise ValueError(f"article content not found for {article_id}")
        entities = self._extractor(content["content"])
        self._database.news_entities.replace_one(
            {"_id": article_id},
            {
                "_id": article_id,
                "entities": entities,
                "model_name": os.getenv("NER_MODEL_NAME", "gliner2"),
                "model_version": os.getenv(
                    "FOOTBALLPULSE_GLINER_MODEL", "fastino/gliner2-large-v1"
                ),
                "processed_at": datetime.now(UTC),
            },
            upsert=True,
        )
        return article_id

    def process_articles(self, article_ids: list[UUID]) -> list[UUID]:
        with ThreadPoolExecutor(max_workers=self._workers) as executor:
            return list(executor.map(self.process_article, article_ids))


class V2NewsCrawledConsumer:
    def __init__(self, *, consumer: Consumer, processor: V2EntityProcessor) -> None:
        self._consumer = consumer
        self._processor = processor
        self._consumer.subscribe([NEWS_CRAWLED_TOPIC])

    def run_once(self, *, timeout_seconds: float = 1.0) -> UUID | None:
        message = self._consumer.poll(timeout_seconds)
        if message is None:
            return None
        if message.error() is not None:
            raise RuntimeError(f"Kafka consumer error: {message.error()}")
        raw = message.value()
        if raw is None:
            raise ValueError("news.crawled payload must not be null")
        event = NewsCrawledEvent.model_validate_json(raw)
        article_id = self._processor.process_article(event.payload.article_id)
        self._consumer.commit(message=message, asynchronous=False)
        return article_id
