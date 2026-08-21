from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from confluent_kafka import Consumer
from footballpulse_event_contracts import NewsCrawledEvent
from footballpulse_runtime_config import log_event
from pymongo.database import Database

from footballpulse_entities_extraction_service.canonical import CanonicalRegistry

LOGGER = logging.getLogger("footballpulse.entities_extraction.processor")
NEWS_CRAWLED_TOPIC = "news.crawled.v1"
MIN_PERSISTED_ENTITY_SCORE = 0.95

EntityPrediction = dict[str, Any]
EntityExtractor = Callable[[str], list[EntityPrediction]]
MongoDocument = dict[str, Any]


class V2EntityProcessor:
    """Processes article pointers, replaces aliases with canonical names, and extracts canonical entities."""

    def __init__(
        self,
        *,
        database: Database[MongoDocument],
        extractor: EntityExtractor,
        registry: CanonicalRegistry | None = None,
        workers: int = 6,
    ) -> None:
        if workers < 1:
            raise ValueError("entity worker count must be positive")
        self._database = database
        self._extractor = extractor
        self._workers = workers
        self._registry = registry or self._load_registry()

    def _load_registry(self) -> CanonicalRegistry:
        docs = list(self._database.canonical_entities.find({"status": "ACTIVE"}))
        log_event(LOGGER, "canonical_registry_loaded", active_entities=len(docs))
        return CanonicalRegistry(docs)

    def process_article(self, article_id: UUID) -> UUID:
        started = time.monotonic()
        log_event(LOGGER, "entity_article_started", article_id=str(article_id))
        content_doc = self._database.news_content.find_one({"_id": article_id})
        if content_doc is None or not isinstance(content_doc.get("content"), str):
            log_event(LOGGER, "entity_article_missing_content", article_id=str(article_id), level=logging.WARNING)
            raise ValueError(f"article content not found for {article_id}")

        raw_content = content_doc["content"]
        filtered_content = self._registry.replace_aliases(raw_content)
        now = datetime.now(UTC)

        # Persist filtered_content to news_content
        self._database.news_content.update_one(
            {"_id": article_id},
            {"$set": {"filtered_content": filtered_content, "filtered_at": now}},
        )

        # Run extraction on filtered_content
        raw_entities = self._extractor(filtered_content)
        canonicalized_entities: list[dict[str, Any]] = []
        skipped_low_score = 0

        for entity in raw_entities:
            text = str(entity.get("text", ""))
            label = str(entity.get("label", "club"))
            score = float(entity.get("score", 1.0))
            start = int(entity.get("start", 0))
            end = int(entity.get("end", 0))
            if score < MIN_PERSISTED_ENTITY_SCORE:
                skipped_low_score += 1
                continue

            can_id, can_name = self._registry.resolve_entity(text, label)
            canonicalized_entities.append(
                {
                    "label": label.upper(),
                    "text": text,
                    "score": score,
                    "start": start,
                    "end": end,
                    "canonical_entity_id": can_id,
                    "canonical_name": can_name,
                }
            )

        self._database.news_entities.replace_one(
            {"_id": article_id},
            {
                "_id": article_id,
                "entities": canonicalized_entities,
                "model_name": os.getenv("NER_MODEL_NAME", "gliner2"),
                "model_version": os.getenv("FOOTBALLPULSE_GLINER_MODEL", "fastino/gliner2-large-v1"),
                "processed_at": now,
            },
            upsert=True,
        )
        log_event(
            LOGGER,
            "entity_article_completed",
            article_id=str(article_id),
            content_chars=len(raw_content),
            filtered_chars=len(filtered_content),
            raw_entities=len(raw_entities),
            persisted_entities=len(canonicalized_entities),
            skipped_low_score=skipped_low_score,
            min_persisted_score=MIN_PERSISTED_ENTITY_SCORE,
            duration_ms=round((time.monotonic() - started) * 1000),
        )
        return article_id

    def process_articles(self, article_ids: list[UUID]) -> list[UUID]:
        if not article_ids:
            log_event(LOGGER, "entity_batch_empty")
            return []
        started = time.monotonic()
        log_event(LOGGER, "entity_batch_started", article_count=len(article_ids), workers=self._workers)
        completed: list[UUID] = []
        with ThreadPoolExecutor(max_workers=self._workers) as executor:
            futures = [executor.submit(self.process_article, article_id) for article_id in article_ids]
            for index, future in enumerate(as_completed(futures), start=1):
                article_id = future.result()
                completed.append(article_id)
                log_event(
                    LOGGER,
                    "entity_batch_progress",
                    completed=index,
                    total=len(article_ids),
                    article_id=str(article_id),
                )
        log_event(
            LOGGER,
            "entity_batch_completed",
            article_count=len(completed),
            duration_ms=round((time.monotonic() - started) * 1000),
        )
        return completed


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
        log_event(
            LOGGER,
            "entity_kafka_message_received",
            topic=message.topic(),
            partition=message.partition(),
            offset=message.offset(),
            article_id=str(event.payload.article_id),
        )
        article_id = self._processor.process_article(event.payload.article_id)
        self._consumer.commit(message=message, asynchronous=False)
        log_event(LOGGER, "entity_kafka_message_committed", article_id=str(article_id))
        return article_id
