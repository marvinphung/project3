from __future__ import annotations

import logging
import re
import unicodedata
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from bson.binary import Binary, UuidRepresentation
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


def normalize_uuid(value: Any) -> UUID:
    if isinstance(value, UUID):
        return value
    if isinstance(value, Binary):
        return value.as_uuid(UuidRepresentation.STANDARD)
    return UUID(str(value))


class V2Publisher:
    """Materializes entity timeline summaries from Mongo into Supabase PostgreSQL read model."""

    def __init__(self, *, mongo: Database[MongoDocument], postgres: Engine) -> None:
        self._mongo = mongo
        self._postgres = postgres

    def _entity_aliases(self, canonical_doc: MongoDocument | None) -> list[str]:
        aliases: list[str] = []
        if canonical_doc:
            for alias_entry in canonical_doc.get("aliases", []):
                val = alias_entry.get("value") if isinstance(alias_entry, dict) else str(alias_entry)
                if val and val not in aliases:
                    aliases.append(val)
        return aliases

    def _canonical_details(
        self,
        entity_id: UUID,
        *,
        fallback_name: str,
        fallback_type: str,
    ) -> tuple[str, str, list[str]]:
        canonical_doc = self._mongo.canonical_entities.find_one({"_id": entity_id})
        if not canonical_doc:
            return fallback_name, normalize_entity_type(fallback_type), []
        canonical_name = str(canonical_doc.get("canonical_name") or fallback_name)
        entity_type = normalize_entity_type(str(canonical_doc.get("entity_type") or fallback_type))
        return canonical_name, entity_type, self._entity_aliases(canonical_doc)

    def _upsert_entity(
        self,
        connection: sa.Connection,
        *,
        entity_id: UUID,
        canonical_name: str,
        entity_type: str,
        aliases: list[str],
        last_seen_at: datetime,
        mention_count_24h: int | None = None,
    ) -> None:
        update_count_sql = ""
        update_count_params_sql = ""
        insert_count_column_sql = ""
        insert_count_value_sql = ""
        params: dict[str, Any] = {
            "id": entity_id,
            "entity_type": normalize_entity_type(entity_type),
            "canonical_name": canonical_name,
            "slug": slugify(canonical_name),
            "aliases": aliases,
            "has_aliases": bool(aliases),
            "last_seen_at": last_seen_at,
        }
        if mention_count_24h is not None:
            update_count_sql = "mention_count_24h = :mention_count_24h,"
            update_count_params_sql = "mention_count_24h = excluded.mention_count_24h,"
            insert_count_column_sql = ", mention_count_24h"
            insert_count_value_sql = ", :mention_count_24h"
            params["mention_count_24h"] = mention_count_24h

        update_result = connection.execute(
            sa.text(
                f"""
                update entities
                set entity_type = cast(:entity_type as entity_type_v2),
                    name = :canonical_name,
                    canonical_name = :canonical_name,
                    slug = :slug,
                    aliases = case when :has_aliases then :aliases else aliases end,
                    last_seen_at = greatest(last_seen_at, :last_seen_at),
                    {update_count_sql}
                    updated_at = now()
                where id = :id
                """
            ),
            params,
        )
        if update_result.rowcount:
            return

        values_sql = f"""
            :id,
            cast(:entity_type as entity_type_v2),
            :canonical_name,
            :canonical_name,
            :slug,
            :aliases,
            :last_seen_at,
            now()
            {insert_count_value_sql}
        """
        columns_sql = f"id, entity_type, name, canonical_name, slug, aliases, last_seen_at, updated_at{insert_count_column_sql}"
        update_count_sql = ""
        if mention_count_24h is not None:
            update_count_sql = update_count_params_sql

        connection.execute(
            sa.text(
                f"""
                insert into entities ({columns_sql})
                values ({values_sql})
                on conflict (entity_type, slug) do update set
                    name = excluded.canonical_name,
                    canonical_name = excluded.canonical_name,
                    aliases = case when array_length(excluded.aliases, 1) > 0 then excluded.aliases else entities.aliases end,
                    last_seen_at = greatest(entities.last_seen_at, excluded.last_seen_at),
                    {update_count_sql}
                    updated_at = now()
                """
            ),
            params,
        )

    def publish_summary(self, summary_id: UUID) -> bool:
        summary = self._mongo.entity_timeline_summaries.find_one({"_id": summary_id})
        if summary is None or summary.get("status") != "COMPLETED":
            return False

        entity_id = summary["entity_id"]
        postgres_summary_id = normalize_uuid(summary_id)
        postgres_entity_id = normalize_uuid(entity_id)
        canonical_name = summary["canonical_name"]
        raw_entity_type = summary.get("entity_type", "CLUB")
        entity_type = normalize_entity_type(raw_entity_type)

        # Lookup aliases from canonical_entities if available
        canonical_doc = self._mongo.canonical_entities.find_one({"_id": entity_id})
        aliases = self._entity_aliases(canonical_doc)

        article_ids = summary.get("article_ids", [])
        articles_metadata = list(self._mongo.news_metadata.find({"_id": {"$in": article_ids}}))
        articles_map = {m["_id"]: m for m in articles_metadata}
        articles_content = list(self._mongo.news_content.find({"_id": {"$in": article_ids}}))
        content_map = {c["_id"]: c for c in articles_content}

        now = datetime.now(UTC)

        with self._postgres.begin() as connection:
            # 1. Upsert entity
            self._upsert_entity(
                connection,
                entity_id=postgres_entity_id,
                entity_type=entity_type,
                canonical_name=canonical_name,
                aliases=aliases,
                last_seen_at=summary["window_end"],
            )

            # 2. Upsert source articles
            for art_id in article_ids:
                meta = articles_map.get(art_id)
                if not meta:
                    continue
                postgres_art_id = normalize_uuid(art_id)
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
                art_slug = f"{slugify(title)}-{str(postgres_art_id)[:8]}"
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
                        "id": postgres_art_id,
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
                    "id": postgres_summary_id,
                    "entity_id": postgres_entity_id,
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
                postgres_art_id = normalize_uuid(art_id)
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
                        "timeline_item_id": postgres_summary_id,
                        "article_id": postgres_art_id,
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
        """Refreshes 24h distinct article mention counts from Mongo extraction results.

        Popularity must not depend on timeline summaries. The UI should show hot entities
        even when content-summary has not generated a timeline item for them yet.
        """
        now = datetime.now(UTC)
        window_start = now - timedelta(hours=24)
        metadata = list(
            self._mongo.news_metadata.find(
                {"crawl_date": {"$gte": window_start, "$lt": now}}
            )
        )
        article_ids = [doc["_id"] for doc in metadata]
        crawled_at_by_article = {doc["_id"]: doc.get("crawl_date") or now for doc in metadata}
        entities_map = {
            doc["_id"]: doc
            for doc in self._mongo.news_entities.find({"_id": {"$in": article_ids}})
        }

        counts: dict[tuple[UUID, str, str], int] = {}
        last_seen: dict[tuple[UUID, str, str], datetime] = {}
        for article_id in article_ids:
            seen_in_article: set[tuple[UUID, str, str]] = set()
            for mention in entities_map.get(article_id, {}).get("entities", []):
                entity_id = mention.get("canonical_entity_id")
                canonical_name = mention.get("canonical_name")
                if not entity_id or not canonical_name:
                    continue
                normalized_id = normalize_uuid(entity_id)
                resolved_name, resolved_type, _aliases = self._canonical_details(
                    normalized_id,
                    fallback_name=str(canonical_name),
                    fallback_type=str(mention.get("label", "CLUB")),
                )
                seen_in_article.add((normalized_id, resolved_name, resolved_type))

            crawl_date = crawled_at_by_article.get(article_id) or now
            for entity_key in seen_in_article:
                counts[entity_key] = counts.get(entity_key, 0) + 1
                last_seen[entity_key] = max(last_seen.get(entity_key, crawl_date), crawl_date)

        with self._postgres.begin() as connection:
            active_entity_ids = list({entity_id for entity_id, _name, _type in counts})
            active_rows: list[dict[str, Any]] = []
            for (entity_id, canonical_name, entity_type), count in counts.items():
                resolved_name, resolved_type, aliases = self._canonical_details(
                    entity_id,
                    fallback_name=canonical_name,
                    fallback_type=entity_type,
                )
                active_rows.append(
                    {
                        "id": entity_id,
                        "entity_type": resolved_type,
                        "canonical_name": resolved_name,
                        "slug": slugify(resolved_name),
                        "aliases": aliases,
                        "last_seen_at": last_seen[(entity_id, canonical_name, entity_type)],
                        "mention_count_24h": count,
                    }
                )

            existing_entity_ids: set[UUID] = set()
            if active_entity_ids:
                existing_rows = connection.execute(
                    sa.text(
                        """
                        select id
                        from entities
                        where id in :active_entity_ids
                        """
                    ).bindparams(sa.bindparam("active_entity_ids", expanding=True)),
                    {"active_entity_ids": active_entity_ids},
                ).mappings().all()
                existing_entity_ids = {normalize_uuid(row["id"]) for row in existing_rows}

            missing_rows = [row for row in active_rows if row["id"] not in existing_entity_ids]
            if missing_rows:
                connection.execute(
                    sa.text(
                        """
                        insert into entities (
                            id, entity_type, name, canonical_name, slug, aliases,
                            last_seen_at, mention_count_24h, updated_at
                        )
                        values (
                            :id,
                            cast(:entity_type as entity_type_v2),
                            :canonical_name,
                            :canonical_name,
                            :slug,
                            :aliases,
                            :last_seen_at,
                            :mention_count_24h,
                            now()
                        )
                        on conflict do nothing
                        """
                    ),
                    missing_rows,
                )

            if active_rows:
                connection.execute(
                    sa.text(
                        """
                        update entities
                        set mention_count_24h = :mention_count_24h,
                            last_seen_at = greatest(last_seen_at, :last_seen_at),
                            updated_at = now()
                        where id = :id
                        """
                    ),
                    active_rows,
                )

            if active_entity_ids:
                connection.execute(
                    sa.text(
                        """
                        update entities
                        set mention_count_24h = 0,
                            updated_at = now()
                        where id not in :active_entity_ids and mention_count_24h != 0;
                        """
                    ).bindparams(sa.bindparam("active_entity_ids", expanding=True)),
                    {"active_entity_ids": active_entity_ids},
                )
            else:
                connection.execute(
                    sa.text(
                        """
                        update entities
                        set mention_count_24h = 0,
                            updated_at = now()
                        where mention_count_24h != 0;
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
