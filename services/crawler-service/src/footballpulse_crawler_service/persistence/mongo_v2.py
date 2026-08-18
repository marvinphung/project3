from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import UUID

from pymongo.database import Database

from footballpulse_crawler_service.extraction.service import ExtractedArticle
from footballpulse_shared import article_id_from_url, canonicalize_news_url

MongoDocument = dict[str, object]


class V2MongoArticleWriter:
    """Writes only the crawl product documents; no crawl state is persisted."""

    def __init__(self, database: Database[MongoDocument]) -> None:
        self._metadata = database.news_metadata
        self._content = database.news_content

    def write(self, article: ExtractedArticle, *, source_name: str) -> UUID | None:
        extraction = article.extraction
        if extraction.text is None or extraction.status.value == "FAILED":
            return None
        canonical_url = canonicalize_news_url(article.final_url)
        article_id = article_id_from_url(canonical_url)
        now = datetime.now(UTC)
        content_hash = hashlib.sha256(extraction.text.encode("utf-8")).hexdigest()
        metadata: MongoDocument = {
            "_id": article_id,
            "url": article.requested_url,
            "canonical_url": canonical_url,
            "domain_name": canonical_url.split("/", 3)[2],
            "source_name": source_name,
            "title": extraction.title or "Untitled",
            "description": None,
            "published_time": None,
            "crawl_date": now,
            "image_url": None,
            "tags": [],
            "article_keywords": [],
            "content_hash": content_hash,
            "language": "en",
        }
        content: MongoDocument = {
            "_id": article_id,
            "content": extraction.text,
            "cleaned_at": now,
            "extractor": extraction.extractor.value if extraction.extractor else "UNKNOWN",
            "extraction_status": extraction.status.value,
        }
        self._metadata.replace_one({"_id": article_id}, metadata, upsert=True)
        self._content.replace_one({"_id": article_id}, content, upsert=True)
        return article_id
