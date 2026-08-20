from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

from footballpulse_runtime_config import log_event
from pymongo.database import Database

from footballpulse_content_summary_service.llm_client import LLMClient, create_llm_client

LOGGER = logging.getLogger("footballpulse.content_summary")
SUMMARY_NAMESPACE = UUID("c384e508-4e31-4e4b-a25e-e4782bbbe528")

PROMPTS_DIR = Path(__file__).parent / "prompts"
TOP_ENTITY_LIMIT = 30
MAX_ARTICLES_PER_ENTITY = 5


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
    filtered_content: str
    crawl_date: datetime
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

    def process_window(
        self,
        window_start: datetime,
        window_end: datetime,
        *,
        force_recompute: bool = False,
    ) -> list[dict[str, Any]]:
        """Processes top entities with articles crawled in [window_start, window_end)."""
        log_event(LOGGER, "summary_window_started", window_start=window_start.isoformat(), window_end=window_end.isoformat())

        top_entities = set(self._get_top_entities(window_end))
        if not top_entities:
            log_event(LOGGER, "summary_no_top_entities", window_end=window_end.isoformat())
            return []

        # 1. Query articles in crawl-date window
        query = {"crawl_date": {"$gte": window_start, "$lt": window_end}}
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
            filtered_content = content_doc.get("filtered_content") or clean_content
            crawl_date = self._to_utc(meta.get("crawl_date") or datetime.now(UTC))
            ent_doc = entities_map.get(aid, {})
            ents = ent_doc.get("entities", [])
            articles.append(
                ArticleInfo(
                    id=aid,
                    title=meta.get("title", ""),
                    content=clean_content,
                    filtered_content=filtered_content,
                    crawl_date=crawl_date,
                    entities=ents,
                )
            )

        # 3. Group by canonical entity
        # entity_key -> (entity_id, canonical_name, entity_type, list[ArticleInfo])
        entity_articles: dict[tuple[UUID, str, str], list[ArticleInfo]] = {}

        for article in articles:
            seen_entities_in_article = set()
            for mention in article.entities:
                ent_key = self._entity_key_from_mention(mention)
                if ent_key is None:
                    continue
                if ent_key not in top_entities:
                    continue
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

            selected_articles = self._select_top_articles_for_entity(ent_articles, canonical_name)
            # LLM sees clean content newest first after the relevance cut.
            sorted_articles = sorted(selected_articles, key=lambda a: a.crawl_date, reverse=True)
            distinct_article_ids = [a.id for a in sorted_articles]

            # Format articles content for the single LLM call.
            articles_text = "\n\n---\n\n".join(
                f"Title: {a.title}\nCrawled: {a.crawl_date.isoformat()}\nContent: {a.content}"
                for a in sorted_articles
            )

            prompt = self._agg_prompt_tmpl.format(
                entity_name=canonical_name,
                entity_type=entity_type,
                articles_content=articles_text,
            )
            llm_result = self._parse_llm_timeline_item(self._llm.generate(prompt))
            short_description = llm_result["title"]
            aggregated_news = llm_result["content"]

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
                "entities_50": [],
                "entities_80": [],
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

    def _get_top_entities(self, window_end: datetime) -> list[tuple[UUID, str, str]]:
        window_end = self._to_utc(window_end)
        window_start = window_end - timedelta(hours=24)
        metadata = list(
            self._database.news_metadata.find(
                {"crawl_date": {"$gte": window_start, "$lt": window_end}}
            )
        )
        if not metadata:
            return []

        article_ids = [m["_id"] for m in metadata]
        entities_map = {e["_id"]: e for e in self._database.news_entities.find({"_id": {"$in": article_ids}})}

        counts: dict[tuple[UUID, str, str], int] = {}
        for article_id in article_ids:
            seen_in_article: set[tuple[UUID, str, str]] = set()
            for mention in entities_map.get(article_id, {}).get("entities", []):
                entity_key = self._entity_key_from_mention(mention)
                if entity_key is not None:
                    seen_in_article.add(entity_key)
            for entity_key in seen_in_article:
                counts[entity_key] = counts.get(entity_key, 0) + 1

        return [
            entity_key
            for entity_key, _count in sorted(
                counts.items(),
                key=lambda item: (-item[1], item[0][1], item[0][2]),
            )[:TOP_ENTITY_LIMIT]
        ]

    def _select_top_articles_for_entity(self, articles: list[ArticleInfo], canonical_name: str) -> list[ArticleInfo]:
        ranked = sorted(
            articles,
            key=lambda article: (
                -self._count_entity_mentions(article.filtered_content, canonical_name),
                -article.crawl_date.timestamp(),
            ),
        )
        return ranked[:MAX_ARTICLES_PER_ENTITY]

    @staticmethod
    def _count_entity_mentions(text: str, entity_name: str) -> int:
        if not text or not entity_name:
            return 0
        pattern = re.compile(rf"(?<!\w){re.escape(entity_name)}(?!\w)", re.IGNORECASE)
        return len(pattern.findall(text))

    @staticmethod
    def _entity_key_from_mention(mention: dict[str, Any]) -> tuple[UUID, str, str] | None:
        can_id = mention.get("canonical_entity_id")
        can_name = mention.get("canonical_name")
        ent_type = mention.get("label", "CLUB").upper()
        if not can_id or not can_name:
            return None
        if not isinstance(can_id, UUID):
            can_id = UUID(str(can_id))
        return can_id, can_name, ent_type

    @staticmethod
    def _parse_llm_timeline_item(raw_response: str) -> dict[str, str]:
        text = raw_response.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        if not text:
            raise ValueError("LLM response was empty")
        try:
            data = json.loads(text)
            title = str(data.get("title", "")).strip()
            content = str(data.get("content", "")).strip()
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, flags=re.DOTALL)
            if match is not None:
                data = json.loads(match.group(0))
                title = str(data.get("title", "")).strip()
                content = str(data.get("content", "")).strip()
            else:
                lines = [line.strip(" #") for line in text.splitlines() if line.strip()]
                title = lines[0][:180] if lines else ""
                content = text
        if not title or not content:
            raise ValueError("LLM response must include non-empty title and content")
        return {"title": title, "content": content}

    @staticmethod
    def _to_utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
