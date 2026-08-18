from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from pymongo import DESCENDING
from pymongo.collection import Collection

from footballpulse_api_gateway.api.editorial_admin import SourceArticlePage, SourceArticleView


class MongoSourceArticleReadRepository:
    """Read-only projection of source articles for the editorial admin UI."""

    def __init__(self, collection: Collection[dict[str, Any]]) -> None:
        self._collection = collection

    def list_source_articles(
        self, *, limit: int, offset: int, query: str | None
    ) -> SourceArticlePage:
        criteria: dict[str, object] = {}
        if query:
            pattern = re.escape(query.strip())
            criteria["$or"] = [
                {"title": {"$regex": pattern, "$options": "i"}},
                {"rss_title": {"$regex": pattern, "$options": "i"}},
                {"canonical_url": {"$regex": pattern, "$options": "i"}},
            ]
        projection = {
            "_id": 1,
            "title": 1,
            "rss_title": 1,
            "canonical_url": 1,
            "collected_at": 1,
            "extraction_status": 1,
            "duplicate_type": 1,
        }
        documents = self._collection.find(criteria, projection).sort(
            "collected_at", DESCENDING
        ).skip(offset).limit(limit)
        return SourceArticlePage(
            items=tuple(self._to_view(document) for document in documents),
            total=self._collection.count_documents(criteria),
        )

    @staticmethod
    def _to_view(document: dict[str, Any]) -> SourceArticleView:
        collected_at = document.get("collected_at")
        if not isinstance(collected_at, datetime):
            collected_at = datetime.fromtimestamp(0, tz=UTC)
        elif collected_at.tzinfo is None:
            collected_at = collected_at.replace(tzinfo=UTC)
        title = document.get("title") or document.get("rss_title") or "Không có tiêu đề"
        source_url = document.get("canonical_url") or ""
        return SourceArticleView(
            id=str(document["_id"]),
            title=str(title),
            source_url=str(source_url),
            collected_at=collected_at,
            extraction_status=str(document.get("extraction_status") or "UNKNOWN"),
            duplicate_type=str(document.get("duplicate_type") or "NONE"),
        )
