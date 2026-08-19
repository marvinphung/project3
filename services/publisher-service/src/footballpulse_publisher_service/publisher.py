from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid5

import sqlalchemy as sa
from pymongo.database import Database
from sqlalchemy.engine import Engine

SOURCE_NAMESPACE = UUID("9f8620af-3c33-49d8-a1c5-0fefadad86f7")
MongoDocument = dict[str, Any]


class V2Publisher:
    """Materialize one fully enriched Mongo article into the public read model."""

    def __init__(self, *, mongo: Database[MongoDocument], postgres: Engine) -> None:
        self._mongo = mongo
        self._postgres = postgres

    def publish_article(self, article_id: UUID) -> bool:
        metadata = self._mongo.news_metadata.find_one({"_id": article_id})
        enrichment = self._mongo.news_enrichments.find_one({"_id": article_id})
        if metadata is None or enrichment is None:
            return False
        if enrichment.get("validation_status") != "VALIDATED":
            return False

        source_id = uuid5(SOURCE_NAMESPACE, str(metadata["domain_name"]))
        story_id = article_id
        now = datetime.now(UTC)
        event_type = str(enrichment.get("event_type", "OTHER"))
        title = str(metadata.get("title", "Untitled"))
        summary_en = str(enrichment.get("summary_en", ""))
        summary_vi = str(enrichment.get("summary_vi", ""))
        slug = f"{metadata['domain_name']}-{article_id}"

        with self._postgres.begin() as connection:
            connection.execute(
                sa.text(
                    """insert into sources (id, name, domain_name, homepage_url, reliability_tier)
                    values (:id, :name, :domain, :homepage, 3)
                    on conflict (id) do update set name = excluded.name,
                    homepage_url = excluded.homepage_url, updated_at = now()"""
                ),
                {"id": source_id, "name": metadata["source_name"], "domain": metadata["domain_name"], "homepage": f"https://{metadata['domain_name']}"},
            )
            connection.execute(
                sa.text(
                    """insert into articles (id, source_id, url, canonical_url, domain_name, title,
                    description, image_url, published_at, crawled_at, language, content_hash,
                    summary_en, summary_vi, event_type)
                    values (:id, :source_id, :url, :canonical_url, :domain, :title, :description,
                    :image_url, :published_at, :crawled_at, :language, :content_hash, :summary_en,
                    :summary_vi, :event_type)
                    on conflict (id) do update set title = excluded.title, summary_en = excluded.summary_en,
                    summary_vi = excluded.summary_vi, event_type = excluded.event_type, updated_at = now()"""
                ),
                {"id": article_id, "source_id": source_id, "url": metadata["url"], "canonical_url": metadata["canonical_url"], "domain": metadata["domain_name"], "title": title, "description": metadata.get("description"), "image_url": metadata.get("image_url"), "published_at": metadata.get("published_time"), "crawled_at": metadata["crawl_date"], "language": metadata.get("language", "en"), "content_hash": metadata["content_hash"], "summary_en": summary_en, "summary_vi": summary_vi, "event_type": event_type},
            )
            connection.execute(
                sa.text(
                    """insert into stories (id, title_en, title_vi, summary_en, summary_vi,
                    event_type, first_seen_at, last_seen_at)
                    values (:id, :title_en, :title_vi, :summary_en, :summary_vi, :event_type, :seen, :seen)
                    on conflict (id) do update set summary_en = excluded.summary_en,
                    summary_vi = excluded.summary_vi, last_seen_at = excluded.last_seen_at"""
                ),
                {"id": story_id, "title_en": title, "title_vi": title, "summary_en": summary_en, "summary_vi": summary_vi, "event_type": event_type, "seen": now},
            )
            connection.execute(
                sa.text(
                    """insert into story_sources (story_id, article_id, source_id)
                    values (:story, :article, :source)
                    on conflict (story_id, article_id) do nothing"""
                ),
                {"story": story_id, "article": article_id, "source": source_id},
            )
            connection.execute(
                sa.text(
                    """insert into publications (id, story_id, slug, title_en, title_vi,
                    excerpt_vi, body_en, body_vi, published_at)
                    values (:id, :story, :slug, :title_en, :title_vi, :excerpt, :body_en, :body_vi, :published)
                    on conflict (slug) do update set title_en = excluded.title_en,
                    title_vi = excluded.title_vi, body_en = excluded.body_en, body_vi = excluded.body_vi,
                    updated_at = now()"""
                ),
                {"id": article_id, "story": story_id, "slug": slug, "title_en": title, "title_vi": title, "excerpt": summary_vi, "body_en": summary_en, "body_vi": summary_vi, "published": now},
            )
        self._mongo.news_enrichments.update_one(
            {"_id": article_id},
            {"$set": {"publish_status": "PUBLISHED", "published_to_postgres_at": now}},
        )
        return True
