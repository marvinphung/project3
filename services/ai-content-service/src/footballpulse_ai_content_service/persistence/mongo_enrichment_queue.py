from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from uuid import UUID

from pymongo import ASCENDING, ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from footballpulse_ai_content_service.contracts.batch import (
    BatchRecord,
    FailedBatchRecord,
    SuccessfulBatchRecord,
)
from footballpulse_ai_content_service.contracts.enrichment import ArticleEnrichmentInput

MongoDocument = dict[str, object]


class MongoEnrichmentQueue:
    def __init__(
        self,
        database: Database[MongoDocument],
        *,
        source_reliability: Callable[[UUID], int],
        clock: Callable[[], datetime],
        max_attempts: int = 3,
        lease_seconds: int = 300,
    ) -> None:
        self._database = database
        self._source_reliability = source_reliability
        self._clock = clock
        self._max_attempts = max_attempts
        self._lease_seconds = lease_seconds

    def ensure_indexes(self) -> None:
        self._database.ai_enrichment_work.create_index(
            [("status", ASCENDING), ("lease_expires_at", ASCENDING)],
            name="ix_ai_enrichment_work_status_lease",
        )

    def claim_pending(self, *, limit: int) -> tuple[ArticleEnrichmentInput, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("claim limit must be between 1 and 100")
        completed_ids = {
            str(item["article_version_id"])
            for item in self._database.article_enrichments.find({}, {"article_version_id": 1})
            if item.get("article_version_id") is not None
        }
        now = self._clock()
        claimed: list[ArticleEnrichmentInput] = []
        candidates = self._database.article_intelligence.find({"status": "COMPLETED"}).sort(
            "processed_at", ASCENDING
        )
        for intelligence in candidates:
            article_id = str(intelligence["article_version_id"])
            if article_id in completed_ids or len(claimed) >= limit:
                continue
            if not self._acquire(article_id, now=now):
                continue
            source = self._database.source_articles.find_one({"article_version_id": article_id})
            if source is None:
                self._record_claim_error(article_id, "SOURCE_ARTICLE_NOT_FOUND", now=now)
                continue
            try:
                claimed.append(self._build_input(source, intelligence))
            except (KeyError, TypeError, ValueError):
                self._record_claim_error(article_id, "INVALID_SOURCE_DOCUMENT", now=now)
        return tuple(claimed)

    def save_records(self, records: tuple[BatchRecord, ...], *, processed_at: datetime) -> None:
        for record in records:
            if isinstance(record, SuccessfulBatchRecord):
                values: MongoDocument = {
                    "status": "COMPLETED",
                    "input_hash": record.result.input_hash,
                    "model_version": record.result.model_version,
                    "prompt_version": record.result.prompt_version,
                    "error_code": None,
                }
            elif isinstance(record, FailedBatchRecord):
                values = {
                    "status": "FAILED",
                    "input_hash": record.input_hash,
                    "error_code": record.error_code,
                }
            else:
                raise TypeError("unsupported provider batch record")
            values["processed_at"] = processed_at
            values["lease_expires_at"] = None
            self._database.ai_enrichment_work.update_one(
                {"_id": str(record.article_version_id)},
                {"$set": values},
            )

    def complete_external(
        self,
        inputs: tuple[ArticleEnrichmentInput, ...],
        *,
        terminal_status: str,
        processed_at: datetime,
    ) -> tuple[int, int]:
        succeeded = 0
        failed = 0
        for source in inputs:
            persisted = self._database.article_enrichments.find_one(
                {
                    "article_version_id": str(source.article_version_id),
                    "input_hash": source.input_hash,
                },
                {"_id": 1},
            )
            if persisted is not None:
                status = "COMPLETED"
                error_code = None
                succeeded += 1
            else:
                status = "FAILED"
                error_code = terminal_status
                failed += 1
            self._database.ai_enrichment_work.update_one(
                {"_id": str(source.article_version_id)},
                {
                    "$set": {
                        "status": status,
                        "input_hash": source.input_hash,
                        "error_code": error_code,
                        "processed_at": processed_at,
                        "lease_expires_at": None,
                    }
                },
            )
        return succeeded, failed

    def _acquire(self, article_id: str, *, now: datetime) -> bool:
        try:
            document = self._database.ai_enrichment_work.find_one_and_update(
                {
                    "_id": article_id,
                    "$and": [
                        {
                            "$or": [
                                {"attempts": {"$lt": self._max_attempts}},
                                {"attempts": {"$exists": False}},
                            ]
                        },
                        {
                            "$or": [
                                {"status": {"$in": ["FAILED", "PENDING"]}},
                                {"lease_expires_at": {"$lte": now}},
                                {"status": {"$exists": False}},
                            ]
                        },
                    ],
                },
                {
                    "$set": {
                        "article_version_id": article_id,
                        "status": "PROCESSING",
                        "lease_expires_at": now + timedelta(seconds=self._lease_seconds),
                    },
                    "$inc": {"attempts": 1},
                },
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
        except DuplicateKeyError:
            return False
        return document is not None

    def _record_claim_error(self, article_id: str, error_code: str, *, now: datetime) -> None:
        self._database.ai_enrichment_work.update_one(
            {"_id": article_id},
            {
                "$set": {
                    "status": "FAILED",
                    "error_code": error_code,
                    "processed_at": now,
                    "lease_expires_at": None,
                }
            },
        )

    def _build_input(
        self,
        source: Mapping[str, object],
        intelligence: Mapping[str, object],
    ) -> ArticleEnrichmentInput:
        article_id = UUID(str(source["article_version_id"]))
        source_id = UUID(str(source["source_id"]))
        entities = intelligence.get("canonical_entities", [])
        if not isinstance(entities, list):
            raise ValueError("canonical entities must be a list")
        published_at = source.get("rss_published_at")
        if isinstance(published_at, str):
            published_at = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        if isinstance(published_at, datetime) and published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=UTC)
        payload: MongoDocument = {
            "contract_version": "article-enrichment.v1",
            "article_version_id": article_id,
            "title": source["title"],
            "cleaned_content": source["cleaned_content"],
            "published_at": published_at,
            "source_id": source_id,
            "source_reliability_tier": self._source_reliability(source_id),
            "canonical_entities": entities,
            "unresolved_mentions": [],
        }
        hash_payload = {
            key: value
            for key, value in payload.items()
            if key not in {"contract_version", "published_at"}
        }
        hash_payload["published_at"] = (
            published_at.isoformat() if isinstance(published_at, datetime) else None
        )
        payload["input_hash"] = hashlib.sha256(
            json.dumps(hash_payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        return ArticleEnrichmentInput.model_validate(payload)
