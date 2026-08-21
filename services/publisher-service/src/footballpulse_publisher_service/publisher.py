from __future__ import annotations

import logging
import re
import unicodedata
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from pymongo.database import Database
from sqlalchemy.engine import Engine

LOGGER = logging.getLogger("footballpulse.publisher")
MongoDocument = dict[str, Any]


def slugify(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value.casefold()).strip("-")
    return slug or "entity"


def normalize_entity_type(raw_type: str) -> str:
    cleaned = raw_type.strip().upper()
    if cleaned in ("PLAYER", "CLUB", "COACH", "COMPETITION"):
        return cleaned
    if cleaned in ("TEAM", "FOOTBALL CLUB"):
        return "CLUB"
    if cleaned in ("MANAGER", "HEAD COACH"):
        return "COACH"
    if cleaned in ("TOURNAMENT", "LEAGUE"):
        return "COMPETITION"
    return "CLUB"


class V2Publisher:
    """Materializes entity timeline summaries from Mongo into Supabase PostgreSQL read model."""

    def __init__(self, *, mongo: Database[MongoDocument], postgres: Engine) -> None:
        self._mongo = mongo
        self._postgres = postgres

    def publish_summary(self, summary_id: UUID) -> bool:
        summary = self._mongo.entity_timeline_summaries.find_one({"_id": summary_id})
        if summary is None or summary.get("status") != "COMPLETED":
            return False

        entity_id = summary["entity_id"]
        canonical_name = summary["canonical_name"]
        raw_entity_type = summary.get("entity_type", "CLUB")
        entity_type = normalize_entity_type(raw_entity_type)
        slug = slugify(canonical_name)

        # Lookup aliases from canonical_entities if available
        canonical_doc = self._mongo.canonical_entities.find_one({"_id": entity_id})
        aliases: list[str] = []
        if canonical_doc:
            for a in canonical_doc.get("aliases", []):
                val = a.get("value") if isinstance(a, dict) else str(a)
                if val and val not in aliases:
                    aliases.append(val)

        article_ids = summary.get("article_ids", [])
        articles_metadata = list(self._mongo.news_metadata.find({"_id": {"$in": article_ids}}))
        articles_map = {m["_id"]: m for m in articles_metadata}
        articles_content = list(self._mongo.news_content.find({"_id": {"$in": article_ids}}))
        content_map = {c["_id"]: c for c in articles_content}

        now = datetime.now(UTC)

        with self._postgres.begin() as connection:
            # 1. Upsert entity
            connection.execute(
                sa.text(
                    """
                    insert into entities (id, entity_type, name, canonical_name, slug, aliases, last_seen_at, updated_at)
                    values (
                        :id,
                        cast(:entity_type as entity_type_v2),
                        :canonical_name,
                        :canonical_name,
                        :slug,
                        :aliases,
                        :last_seen_at,
                        now()
                    )
                    on conflict (entity_type, slug) do update set
                        name = excluded.canonical_name,
                        canonical_name = excluded.canonical_name,
                        aliases = case when array_length(excluded.aliases, 1) > 0 then excluded.aliases else entities.aliases end,
                        last_seen_at = greatest(entities.last_seen_at, excluded.last_seen_at),
                        updated_at = now()
                    """
                ),
                {
                    "id": entity_id,
                    "entity_type": entity_type,
                    "canonical_name": canonical_name,
                    "slug": slug,
                    "aliases": aliases,
                    "last_seen_at": summary["window_end"],
                },
            )

            # 2. Upsert source articles
            for art_id in article_ids:
                meta = articles_map.get(art_id)
                if not meta:
                    continue
                pub_time = meta.get("published_time")
                crawl_date = meta.get("crawl_date") or now
                content_doc = content_map.get(art_id)
                body = (
                    content_doc.get("filtered_content")
                    or content_doc.get("content")
                    if content_doc
                    else None
                )
                if not body:
                    body = meta.get("description") or meta.get("title", "")
                description = meta.get("description")
                excerpt = description or (body[:240] if body else None)
                title = meta.get("title", "Untitled")
                art_slug = f"{slugify(title)}-{str(art_id)[:8]}"
                language = meta.get("language") or "en"

                connection.execute(
                    sa.text(
                        """
                        insert into source_articles (
                            id, title, url, canonical_url, source_name, domain_name,
                            description, image_url, published_at, crawled_at, content_hash,
                            slug, body, excerpt, language, updated_at
                        )
                        values (
                            :id, :title, :url, :canonical_url, :source_name, :domain_name,
                            :description, :image_url, :published_at, :crawled_at, :content_hash,
                            :slug, :body, :excerpt, :language, now()
                        )
                        on conflict (canonical_url) do update set
                            title = excluded.title,
                            description = excluded.description,
                            image_url = excluded.image_url,
                            published_at = excluded.published_at,
                            slug = coalesce(source_articles.slug, excluded.slug),
                            body = coalesce(excluded.body, source_articles.body),
                            excerpt = coalesce(excluded.excerpt, source_articles.excerpt),
                            language = coalesce(excluded.language, source_articles.language),
                            updated_at = now()
                        """
                    ),
                    {
                        "id": art_id,
                        "title": title,
                        "url": meta.get("url", ""),
                        "canonical_url": meta.get("canonical_url", meta.get("url", "")),
                        "source_name": meta.get("source_name", "Unknown"),
                        "domain_name": meta.get("domain_name", "unknown.com"),
                        "description": description,
                        "image_url": meta.get("image_url"),
                        "published_at": pub_time,
                        "crawled_at": crawl_date,
                        "content_hash": meta.get("content_hash", ""),
                        "slug": art_slug,
                        "body": body,
                        "excerpt": excerpt,
                        "language": language,
                    },
                )

            # 3. Upsert entity timeline item
            connection.execute(
                sa.text(
                    """
                    insert into entity_timeline_items (
                        id, entity_id, window_start, window_end, title, summary,
                        article_count, key_entities_50, key_entities_80, updated_at
                    )
                    values (
                        :id, :entity_id, :window_start, :window_end, :title, :summary,
                        :article_count, :key_entities_50, :key_entities_80, now()
                    )
                    on conflict (entity_id, window_start, window_end) do update set
                        title = excluded.title,
                        summary = excluded.summary,
                        article_count = excluded.article_count,
                        key_entities_50 = excluded.key_entities_50,
                        key_entities_80 = excluded.key_entities_80,
                        updated_at = now()
                    """
                ),
                {
                    "id": summary_id,
                    "entity_id": entity_id,
                    "window_start": summary["window_start"],
                    "window_end": summary["window_end"],
                    "title": summary.get("short_description") or canonical_name,
                    "summary": summary.get("aggregated_news") or "",
                    "article_count": max(1, summary.get("article_count", len(article_ids))),
                    "key_entities_50": summary.get("entities_50", []),
                    "key_entities_80": summary.get("entities_80", []),
                },
            )

            # 4. Upsert timeline item articles mapping
            for pos, art_id in enumerate(article_ids):
                connection.execute(
                    sa.text(
                        """
                        insert into timeline_item_articles (timeline_item_id, article_id, position)
                        values (:timeline_item_id, :article_id, :position)
                        on conflict (timeline_item_id, article_id) do update set
                            position = excluded.position
                        """
                    ),
                    {
                        "timeline_item_id": summary_id,
                        "article_id": art_id,
                        "position": pos,
                    },
                )

        # Mark as published in Mongo
        self._mongo.entity_timeline_summaries.update_one(
            {"_id": summary_id},
            {"$set": {"published_at": now}},
        )
        return True

    def refresh_popularity_scores(self) -> None:
        """Refreshes 24h distinct article mention counts for all entities."""
        with self._postgres.begin() as connection:
            connection.execute(
                sa.text(
                    """
                    with popularity as (
                        select
                            eti.entity_id,
                            count(distinct tia.article_id) as count_24h
                        from entity_timeline_items eti
                        join timeline_item_articles tia on tia.timeline_item_id = eti.id
                        join source_articles sa on sa.id = tia.article_id
                        where coalesce(sa.published_at, sa.crawled_at) >= now() - interval '24 hours'
                        group by eti.entity_id
                    )
                    update entities e
                    set mention_count_24h = coalesce(p.count_24h, 0),
                        updated_at = now()
                    from popularity p
                    where e.id = p.entity_id;
                    """
                )
            )
            # Reset entities not active in 24h to 0
            connection.execute(
                sa.text(
                    """
                    update entities
                    set mention_count_24h = 0,
                        updated_at = now()
                    where id not in (
                        select distinct eti.entity_id
                        from entity_timeline_items eti
                        join timeline_item_articles tia on tia.timeline_item_id = eti.id
                        join source_articles sa on sa.id = tia.article_id
                        where coalesce(sa.published_at, sa.crawled_at) >= now() - interval '24 hours'
                    ) and mention_count_24h != 0;
                    """
                )
            )

    def publish_pending(self, limit: int = 50) -> int:
        """Publishes unpublished completed summaries up to limit, then refreshes popularity."""
        cursor = self._mongo.entity_timeline_summaries.find(
            {"status": "COMPLETED", "published_at": None}
        ).sort("window_start", 1).limit(limit)

        published_count = 0
        for doc in cursor:
            if self.publish_summary(doc["_id"]):
                published_count += 1

        if published_count > 0:
            self.refresh_popularity_scores()

        return published_count

    def backfill_source_articles(self) -> int:
        """Backfills missing slug, body, excerpt, language for existing source_articles."""
        with self._postgres.connect() as connection:
            rows = connection.execute(
                sa.text(
                    """
                    select id, title, description, url, canonical_url
                    from source_articles
                    where slug is null or body is null or excerpt is null
                    """
                )
            ).mappings().all()

        if not rows:
            return 0

        art_ids = [row["id"] for row in rows]
        articles_metadata = list(self._mongo.news_metadata.find({"_id": {"$in": art_ids}}))
        articles_map = {m["_id"]: m for m in articles_metadata}
        articles_content = list(self._mongo.news_content.find({"_id": {"$in": art_ids}}))
        content_map = {c["_id"]: c for c in articles_content}

        updated = 0
        with self._postgres.begin() as connection:
            for row in rows:
                art_id = row["id"]
                meta = articles_map.get(art_id, {})
                content_doc = content_map.get(art_id)
                body = (
                    content_doc.get("filtered_content")
                    or content_doc.get("content")
                    if content_doc
                    else None
                )
                if not body:
                    body = meta.get("description") or row.get("description") or row.get("title") or ""
                description = meta.get("description") or row.get("description")
                excerpt = description or (body[:240] if body else None)
                title = row.get("title") or meta.get("title", "Untitled")
                art_slug = f"{slugify(title)}-{str(art_id)[:8]}"
                language = meta.get("language") or "en"

                connection.execute(
                    sa.text(
                        """
                        update source_articles
                        set slug = coalesce(slug, :slug),
                            body = coalesce(body, :body),
                            excerpt = coalesce(excerpt, :excerpt),
                            language = coalesce(language, :language),
                            updated_at = now()
                        where id = :id
                        """
                    ),
                    {
                        "id": art_id,
                        "slug": art_slug,
                        "body": body,
                        "excerpt": excerpt,
                        "language": language,
                    },
                )
                updated += 1

        return updated
