from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from urllib.parse import urlsplit
from uuid import UUID

from pymongo.database import Database

from footballpulse_crawler_service.extraction.service import ExtractedArticle
from footballpulse_shared import article_id_from_url, canonicalize_news_url

MongoDocument = dict[str, object]


class V2MongoArticleWriter:
    """Writes only the crawl product documents; no crawl state is persisted."""

    def __init__(self, database: Database[MongoDocument]) -> None:
        self._database = database
        self._metadata = database.news_metadata
        self._content = database.news_content

    def metadata_exists(self, article_id: UUID) -> bool:
        return self._metadata.find_one({"_id": article_id}, {"_id": 1}) is not None

    def content_exists(self, article_id: UUID) -> bool:
        return self._content.find_one({"_id": article_id}, {"_id": 1}) is not None

    def seed_metadata(
        self,
        *,
        url: str,
        source_name: str,
        title: str,
        published_time: datetime | None = None,
        description: str | None = None,
        image_url: str | None = None,
    ) -> UUID | None:
        """Step 1: Seed article metadata into news_metadata if not already existing."""
        canonical_url = canonicalize_news_url(url)
        article_id = article_id_from_url(canonical_url)
        if self.metadata_exists(article_id):
            return None

        now = datetime.now(UTC)
        domain_name = urlsplit(canonical_url).hostname or canonical_url.split("/", 3)[2]
        metadata: MongoDocument = {
            "_id": article_id,
            "url": url,
            "canonical_url": canonical_url,
            "domain_name": domain_name,
            "source_name": source_name,
            "title": (title or "Untitled").strip()[:500],
            "description": description.strip()[:1000] if description else None,
            "published_time": published_time,
            "crawl_date": now,
            "image_url": image_url.strip() if image_url else None,
            "tags": [],
            "article_keywords": [],
            "content_hash": "",
            "language": "en",
        }
        self._metadata.insert_one(metadata)
        return article_id

    def get_unextracted_articles(
        self,
        *,
        limit: int | None = None,
        source_names: tuple[str, ...] | None = None,
    ) -> list[MongoDocument]:
        """Step 2: Query news_metadata records that do not have corresponding news_content."""
        match_stage: dict[str, object] = {"content_match": {"$size": 0}}
        if source_names:
            match_stage["source_name"] = {"$in": list(source_names)}

        pipeline: list[dict[str, object]] = [
            {
                "$lookup": {
                    "from": "news_content",
                    "localField": "_id",
                    "foreignField": "_id",
                    "as": "content_match",
                }
            },
            {"$match": match_stage},
            {"$sort": {"crawl_date": -1, "_id": 1}},
        ]
        if limit is not None and limit > 0:
            pipeline.append({"$limit": limit})

        return list(self._metadata.aggregate(pipeline))

    def write_content(
        self,
        *,
        article_id: UUID,
        content_text: str,
        extractor: str,
        extraction_status: str,
        title: str | None = None,
    ) -> bool:
        """Step 2: Save cleaned article content into news_content and update news_metadata."""
        if not content_text or extraction_status == "FAILED":
            return False

        now = datetime.now(UTC)
        content_hash = hashlib.sha256(content_text.encode("utf-8")).hexdigest()
        content: MongoDocument = {
            "_id": article_id,
            "content": content_text,
            "cleaned_at": now,
            "extractor": extractor,
            "extraction_status": extraction_status,
        }
        self._content.replace_one({"_id": article_id}, content, upsert=True)

        update_fields: dict[str, object] = {"content_hash": content_hash}
        if title and title.strip():
            existing = self._metadata.find_one({"_id": article_id}, {"title": 1})
            if existing and (not existing.get("title") or existing.get("title") == "Untitled"):
                update_fields["title"] = title.strip()[:500]

        self._metadata.update_one({"_id": article_id}, {"$set": update_fields})
        return True

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

