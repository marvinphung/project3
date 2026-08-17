from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from pymongo import ASCENDING
from pymongo.database import Database

from footballpulse_intelligence_service.application.article_preprocessing import (
    ArticleIntelligenceResult,
    SourceArticle,
)

MongoDocument = dict[str, object]


class MongoArticleIntelligenceRepository:
    def __init__(self, database: Database[MongoDocument], *, max_attempts: int = 3) -> None:
        if max_attempts < 1:
            raise ValueError("max attempts must be positive")
        self._database = database
        self._max_attempts = max_attempts

    def ensure_indexes(self) -> None:
        self._database.article_intelligence.create_index(
            [("article_version_id", ASCENDING)],
            unique=True,
            name="uq_article_intelligence_version",
        )

    def claim_pending(self, *, limit: int) -> list[SourceArticle]:
        if not 1 <= limit <= 256:
            raise ValueError("claim limit must be between 1 and 256")
        terminal = self._database.article_intelligence.find(
            {
                "$or": [
                    {"status": "COMPLETED"},
                    {"status": "FAILED", "attempts": {"$gte": self._max_attempts}},
                ]
            },
            {"article_version_id": 1},
        )
        excluded = [item["article_version_id"] for item in terminal]
        query: dict[str, object] = {
            "extraction_status": "SUCCESS",
            "duplicate_type": {"$ne": "EXACT"},
        }
        if excluded:
            query["article_version_id"] = {"$nin": excluded}
        documents = (
            self._database.source_articles.find(query)
            .sort([("collected_at", ASCENDING), ("article_version_id", ASCENDING)])
            .limit(limit)
        )
        return [self._source_article(document) for document in documents]

    def save_result(self, result: ArticleIntelligenceResult) -> None:
        document: MongoDocument = {
            "_id": str(result.article_version_id),
            "article_version_id": str(result.article_version_id),
            "status": result.status,
            "canonical_entities": [
                {
                    "entity_id": str(entity.entity_id),
                    "entity_type": entity.entity_type.value,
                    "canonical_name": entity.canonical_name,
                }
                for entity in result.canonical_entities
            ],
            "entity_model_name": result.entity_model_name,
            "entity_model_version": result.entity_model_version,
            "embedding_id": str(result.embedding_id) if result.embedding_id else None,
            "embedding_input_hash": result.embedding_input_hash,
            "error_type": result.error_type,
            "processed_at": result.processed_at,
        }
        self._database.article_intelligence.update_one(
            {"_id": document["_id"]},
            {"$set": document, "$inc": {"attempts": 1}},
            upsert=True,
        )

    @staticmethod
    def _source_article(document: Mapping[str, object]) -> SourceArticle:
        article_id = document.get("article_version_id")
        title = document.get("title")
        content = document.get("cleaned_content")
        if (
            not isinstance(article_id, str)
            or not isinstance(title, str)
            or not isinstance(content, str)
        ):
            raise ValueError("source article document is missing required fields")
        return SourceArticle(UUID(article_id), title, content)
