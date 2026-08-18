from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from confluent_kafka import Producer
from pymongo.database import Database

NEWS_ENRICHED_TOPIC = "news.enriched.v1"
MongoDocument = dict[str, Any]


class V2EnrichmentSink:
    """Persists validated Kaggle output and emits a lightweight pointer event."""

    def __init__(self, *, database: Database[MongoDocument], producer: Producer) -> None:
        self._collection = database.news_enrichments
        self._producer = producer

    def persist_validated(self, *, article_id: UUID, output: MongoDocument) -> bool:
        if output.get("validation_status") != "VALIDATED":
            return False
        claims = output.get("claims", [])
        if not isinstance(claims, list):
            return False
        document = {
            "_id": article_id,
            "event_type": str(output.get("event_type", "OTHER")),
            "summary_en": str(output.get("summary_en", "")),
            "summary_vi": str(output.get("summary_vi", "")),
            "claims": claims,
            "validation_status": "VALIDATED",
            "model_name": str(output.get("model_name", "qwen3")),
            "model_version": str(output.get("model_version", "configured-runtime")),
            "prompt_version": str(output.get("prompt_version", "article-enrichment-v1")),
            "processed_at": datetime.now(UTC),
        }
        self._collection.replace_one({"_id": article_id}, document, upsert=True)
        event = {
            "event_type": "news.enriched",
            "event_version": 1,
            "article_id": str(article_id),
            "occurred_at": datetime.now(UTC).isoformat(),
        }
        self._producer.produce(
            NEWS_ENRICHED_TOPIC,
            key=str(article_id).encode("ascii"),
            value=json.dumps(event, separators=(",", ":")).encode("utf-8"),
        )
        self._producer.flush(10)
        return True
