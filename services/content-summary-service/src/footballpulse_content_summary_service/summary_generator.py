from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

from footballpulse_runtime_config import log_event
from pymongo.database import Database

from footballpulse_content_summary_service.llm_client import LLMClient, create_llm_client
from footballpulse_content_summary_service.thresholds import compute_entity_thresholds

LOGGER = logging.getLogger("footballpulse.content_summary")
SUMMARY_NAMESPACE = UUID("c384e508-4e31-4e4b-a25e-e4782bbbe528")

PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt_template(filename: str) -> str:
    path = PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8")


def deterministic_summary_id(entity_id: UUID, window_start: datetime, window_end: datetime) -> UUID:
    key = f"{entity_id}:{window_start.isoformat()}:{window_end.isoformat()}"
    return uuid5(SUMMARY_NAMESPACE, key)


@dataclass(frozen=True, slots=True)
class ArticleInfo:
    id: UUID
    title: str
    content: str
    published_time: datetime
    entities: list[dict[str, Any]]


class SummaryGenerator:
    """Generates per-entity per-window timeline summaries."""

    def __init__(
        self,
        *,
        database: Database[dict[str, Any]],
        llm_client: LLMClient | None = None,
    ) -> None:
        self._database = database
        self._llm = llm_client or create_llm_client()
        self._agg_prompt_tmpl = load_prompt_template("aggregated_news.txt")
        self._desc_prompt_tmpl = load_prompt_template("short_description.txt")

    def process_window(
        self,
        window_start: datetime,
        window_end: datetime,
        *,
        force_recompute: bool = False,
    ) -> list[dict[str, Any]]:
        """Processes all entities with articles in [window_start, window_end)."""
        log_event(LOGGER, "summary_window_started", window_start=window_start.isoformat(), window_end=window_end.isoformat())

        # 1. Query articles in window
        query = {
            "$or": [
                {"published_time": {"$gte": window_start, "$lt": window_end}},
                {"published_time": None, "crawl_date": {"$gte": window_start, "$lt": window_end}},
            ]
        }
        metadata_cursor = self._database.news_metadata.find(query)
        metadata_list = list(metadata_cursor)
        if not metadata_list:
            log_event(LOGGER, "summary_window_empty", window_start=window_start.isoformat())
            return []

        article_ids = [m["_id"] for m in metadata_list]

        # 2. Fetch contents and entities
        contents_map = {c["_id"]: c for c in self._database.news_content.find({"_id": {"$in": article_ids}})}
        entities_map = {e["_id"]: e for e in self._database.news_entities.find({"_id": {"$in": article_ids}})}

        articles: list[ArticleInfo] = []
        for meta in metadata_list:
            aid = meta["_id"]
            content_doc = contents_map.get(aid, {})
            # LLM prompt uses clean_content (content field)
            clean_content = content_doc.get("content") or meta.get("title", "")
            pub_time = meta.get("published_time") or meta.get("crawl_date") or datetime.now(UTC)
            if pub_time.tzinfo is None:
                pub_time = pub_time.replace(tzinfo=UTC)
            ent_doc = entities_map.get(aid, {})
            ents = ent_doc.get("entities", [])
            articles.append(
                ArticleInfo(
                    id=aid,
                    title=meta.get("title", ""),
                    content=clean_content,
                    published_time=pub_time,
                    entities=ents,
                )
            )

        # 3. Group by canonical entity
        # entity_key -> (entity_id, canonical_name, entity_type, list[ArticleInfo])
        entity_articles: dict[tuple[UUID, str, str], list[ArticleInfo]] = {}

        for article in articles:
            seen_entities_in_article = set()
            for mention in article.entities:
                can_id = mention.get("canonical_entity_id")
                can_name = mention.get("canonical_name")
                ent_type = mention.get("label", "CLUB").upper()

                if not can_id or not can_name:
                    continue
                if not isinstance(can_id, UUID):
                    can_id = UUID(str(can_id))

                ent_key = (can_id, can_name, ent_type)
                if ent_key not in seen_entities_in_article:
                    seen_entities_in_article.add(ent_key)
                    if ent_key not in entity_articles:
                        entity_articles[ent_key] = []
                    entity_articles[ent_key].append(article)

        generated_summaries: list[dict[str, Any]] = []

        # 4. Generate summaries per entity
        for (entity_id, canonical_name, entity_type), ent_articles in entity_articles.items():
            summary_id = deterministic_summary_id(entity_id, window_start, window_end)

            if not force_recompute:
                existing = self._database.entity_timeline_summaries.find_one(
                    {"_id": summary_id, "status": "COMPLETED"}
                )
                if existing:
                    log_event(
                        LOGGER,
                        "summary_skipped_existing",
                        entity=canonical_name,
                        summary_id=str(summary_id),
                    )
                    generated_summaries.append(existing)
                    continue

            # Sort articles newest first
            sorted_articles = sorted(ent_articles, key=lambda a: a.published_time, reverse=True)
            distinct_article_ids = [a.id for a in sorted_articles]

            # Compute threshold canonical entities
            article_entities_list = [
                [m.get("canonical_name", "") for m in a.entities if m.get("canonical_name")]
                for a in sorted_articles
            ]
            entities_50, entities_80 = compute_entity_thresholds(article_entities_list)

            # Format articles content for Call 1
            articles_text = "\n\n---\n\n".join(
                f"Title: {a.title}\nPublished: {a.published_time.isoformat()}\nContent: {a.content}"
                for a in sorted_articles
            )

            # LLM Call 1: Aggregated News
            call1_prompt = self._agg_prompt_tmpl.format(
                entity_name=canonical_name,
                entity_type=entity_type,
                articles_content=articles_text,
                entities_50=", ".join(entities_50) if entities_50 else "None",
            )
            aggregated_news = self._llm.generate(call1_prompt)

            # LLM Call 2: Short Description / Title
            call2_prompt = self._desc_prompt_tmpl.format(
                entity_name=canonical_name,
                entity_type=entity_type,
                aggregated_news=aggregated_news,
                entities_80=", ".join(entities_80) if entities_80 else "None",
            )
            short_description = self._llm.generate(call2_prompt)

            now = datetime.now(UTC)
            summary_doc = {
                "_id": summary_id,
                "entity_id": entity_id,
                "canonical_name": canonical_name,
                "entity_type": entity_type,
                "window_start": window_start,
                "window_end": window_end,
                "article_ids": distinct_article_ids,
                "article_count": len(distinct_article_ids),
                "entities_50": entities_50,
                "entities_80": entities_80,
                "aggregated_news": aggregated_news,
                "short_description": short_description,
                "status": "COMPLETED",
                "published_at": None,
                "created_at": now,
                "updated_at": now,
            }

            self._database.entity_timeline_summaries.replace_one(
                {"_id": summary_id},
                summary_doc,
                upsert=True,
            )
            generated_summaries.append(summary_doc)
            log_event(
                LOGGER,
                "summary_generated",
                entity=canonical_name,
                article_count=len(distinct_article_ids),
                summary_id=str(summary_id),
            )

        return generated_summaries
