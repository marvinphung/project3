from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any
from uuid import UUID

import pytest

from footballpulse_crawler_service.discovery.v2_policy import is_within_age_limit
from footballpulse_crawler_service.extraction.processor import ArticleContentProcessor
from footballpulse_crawler_service.persistence.mongo_v2 import V2MongoArticleWriter
from footballpulse_shared import article_id_from_url, canonicalize_news_url

ROOT = Path(__file__).resolve().parents[3]


def _load_crawler_runner() -> ModuleType:
    script_path = ROOT / "scripts" / "run-real-crawl.py"
    spec = importlib.util.spec_from_file_location("footballpulse_real_crawl", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeMongoCollection:
    def __init__(self, db: FakeMongoDatabase, name: str) -> None:
        self._db = db
        self._name = name
        self._docs: dict[Any, dict[str, Any]] = {}

    def find_one(self, filter_query: dict[str, Any], projection: dict[str, Any] | None = None) -> dict[str, Any] | None:
        for doc in self._docs.values():
            if all(doc.get(k) == v for k, v in filter_query.items()):
                if projection and list(projection.values()) == [1]:
                    return {k: doc[k] for k in projection if k in doc}
                return dict(doc)
        return None

    def insert_one(self, document: dict[str, Any]) -> None:
        doc_id = document.get("_id")
        if doc_id in self._docs:
            raise ValueError(f"Duplicate key: {doc_id}")
        self._docs[doc_id] = dict(document)

    def replace_one(self, filter_query: dict[str, Any], replacement: dict[str, Any], upsert: bool = False) -> None:
        doc_id = filter_query.get("_id")
        if doc_id in self._docs or upsert:
            self._docs[doc_id] = dict(replacement)

    def update_one(self, filter_query: dict[str, Any], update: dict[str, Any]) -> None:
        doc_id = filter_query.get("_id")
        if doc_id in self._docs:
            if "$set" in update:
                self._docs[doc_id].update(update["$set"])

    def count_documents(self, filter_query: dict[str, Any]) -> int:
        if not filter_query:
            return len(self._docs)
        count = 0
        for doc in self._docs.values():
            if all(doc.get(k) == v for k, v in filter_query.items()):
                count += 1
        return count

    def aggregate(self, pipeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
        results = [dict(d) for d in self._docs.values()]
        for stage in pipeline:
            if "$lookup" in stage:
                foreign_col = self._db._collections[stage["$lookup"]["from"]]
                local_field = stage["$lookup"]["localField"]
                as_field = stage["$lookup"]["as"]
                for r in results:
                    val = r.get(local_field)
                    matches = [dict(f) for f in foreign_col._docs.values() if f.get("_id") == val]
                    r[as_field] = matches
            elif "$match" in stage:
                match_spec = stage["$match"]
                filtered = []
                for r in results:
                    ok = True
                    for k, v in match_spec.items():
                        if isinstance(v, dict) and "$size" in v:
                            if len(r.get(k, [])) != v["$size"]:
                                ok = False
                                break
                        elif isinstance(v, dict) and "$in" in v:
                            if r.get(k) not in v["$in"]:
                                ok = False
                                break
                        elif r.get(k) != v:
                            ok = False
                            break
                    if ok:
                        filtered.append(r)
                results = filtered
            elif "$limit" in stage:
                results = results[: stage["$limit"]]
        return results


class FakeMongoDatabase:
    def __init__(self) -> None:
        self._collections: dict[str, FakeMongoCollection] = {}

    def __getattr__(self, name: str) -> FakeMongoCollection:
        if name not in self._collections:
            self._collections[name] = FakeMongoCollection(self, name)
        return self._collections[name]


def test_age_limit_30_days_filter() -> None:
    now = datetime(2026, 8, 20, 12, 0, 0, tzinfo=UTC)

    # Fresh article: 2 days old
    fresh = now - timedelta(days=2)
    assert is_within_age_limit(fresh, max_days=30, reference_time=now) is True

    # Boundary article: 29 days old
    boundary = now - timedelta(days=29, hours=23)
    assert is_within_age_limit(boundary, max_days=30, reference_time=now) is True

    # Expired article: 31 days old
    expired = now - timedelta(days=31)
    assert is_within_age_limit(expired, max_days=30, reference_time=now) is False

    # Expired article: 60 days old
    very_old = now - timedelta(days=60)
    assert is_within_age_limit(very_old, max_days=30, reference_time=now) is False

    # Missing date should be accepted
    assert is_within_age_limit(None, max_days=30, reference_time=now) is True


def test_step1_seed_metadata_and_deduplication() -> None:
    db = FakeMongoDatabase()
    writer = V2MongoArticleWriter(db)  # type: ignore[arg-type]

    url = "https://www.bbc.co.uk/sport/football/articles/cp8edryd7plo?utm_source=rss"
    pub_time = datetime(2026, 8, 20, 8, 0, 0, tzinfo=UTC)

    # First seed: should succeed and create news_metadata
    article_id = writer.seed_metadata(
        url=url,
        source_name="BBC Sport - Premier League",
        title="Premier League predictions 2026-27",
        published_time=pub_time,
        description="BBC Sport pundits pick their top four.",
        image_url="https://ichef.bbci.co.uk/sample.jpg",
    )

    assert article_id is not None
    expected_id = article_id_from_url(canonicalize_news_url(url))
    assert article_id == expected_id

    # Verify news_metadata content
    meta = db.news_metadata.find_one({"_id": article_id})
    assert meta is not None
    assert meta["title"] == "Premier League predictions 2026-27"
    assert meta["domain_name"] == "www.bbc.co.uk"
    assert meta["published_time"] == pub_time
    assert meta["content_hash"] == ""
    assert meta["image_url"] == "https://ichef.bbci.co.uk/sample.jpg"

    # Second seed with same URL (or different query params): should return None (deduplicated)
    duplicate_id = writer.seed_metadata(
        url="https://www.bbc.co.uk/sport/football/articles/cp8edryd7plo?utm_campaign=another",
        source_name="BBC Sport - Premier League",
        title="Updated Title",
        published_time=pub_time,
    )
    assert duplicate_id is None
    assert db.news_metadata.count_documents({}) == 1


def test_step2_get_unextracted_articles_and_write_content() -> None:
    db = FakeMongoDatabase()
    writer = V2MongoArticleWriter(db)  # type: ignore[arg-type]

    # Seed 3 articles
    id1 = writer.seed_metadata(
        url="https://www.theguardian.com/football/2026/aug/20/article-1",
        source_name="The Guardian Football",
        title="Article 1",
    )
    id2 = writer.seed_metadata(
        url="https://www.theguardian.com/football/2026/aug/20/article-2",
        source_name="The Guardian Football",
        title="Article 2",
    )
    id3 = writer.seed_metadata(
        url="https://www.theguardian.com/football/2026/aug/20/article-3",
        source_name="The Guardian Football",
        title="Article 3",
    )

    assert id1 and id2 and id3

    # All 3 are unextracted initially
    unextracted = writer.get_unextracted_articles()
    assert len(unextracted) == 3

    # Extract article 1
    content_text = "This is the full cleaned article text for article 1 with high quality content."
    saved = writer.write_content(
        article_id=id1,
        content_text=content_text,
        extractor="TRAFILATURA",
        extraction_status="SUCCESS",
    )
    assert saved is True

    # Verify news_content document
    content_doc = db.news_content.find_one({"_id": id1})
    assert content_doc is not None
    assert content_doc["content"] == content_text
    assert content_doc["extractor"] == "TRAFILATURA"
    assert content_doc["extraction_status"] == "SUCCESS"

    # Verify news_metadata content_hash was updated
    updated_meta = db.news_metadata.find_one({"_id": id1})
    assert len(updated_meta["content_hash"]) == 64

    # Now unextracted count should be 2
    remaining = writer.get_unextracted_articles()
    assert len(remaining) == 2
    remaining_ids = {doc["_id"] for doc in remaining}
    assert remaining_ids == {id2, id3}


def test_catalog_matches_domain_sources_reference() -> None:
    runner = _load_crawler_runner()
    
    enabled_sources = runner.select_sources(None)
    enabled_names = [s.name for s in enabled_sources]
    
    # Verify all 8 BBC RSS feeds are enabled and marked with requires_article_path
    bbc_sources = [s for s in enabled_sources if "BBC Sport" in s.name]
    assert len(bbc_sources) == 8
    for bbc in bbc_sources:
        assert bbc.requires_article_path is True
        assert "bbci.co.uk" in bbc.domains or "bbc.co.uk" in bbc.domains
    
    # Verify Guardian, Athletic (NYTimes), Telegraph, Independent are present and enabled
    assert "The Guardian Football" in enabled_names
    assert "The Athletic Football" in enabled_names
    assert "The Telegraph Football" in enabled_names
    assert "The Independent Football" in enabled_names
    
    # Verify non-RSS / unverified sources are disabled by default
    disabled_sources = [s for s in runner.CATALOG if not s.enabled_by_default]
    disabled_names = [s.name for s in disabled_sources]
    assert "Reuters Soccer" in disabled_names
    assert "ESPN Soccer" in disabled_names
    assert "Sky Sports Football" in disabled_names


def test_bbc_article_url_filtering() -> None:
    runner = _load_crawler_runner()

    bbc_source = next(s for s in runner.CATALOG if "BBC Sport - Premier League" in s.name)
    
    # Valid BBC article URLs
    assert runner._is_valid_article_url(bbc_source, "https://www.bbc.co.uk/sport/football/articles/cp8edryd7plo") is True
    assert runner._is_valid_article_url(bbc_source, "https://www.bbc.com/sport/football/articles/c4g31egre74o?at_medium=RSS") is True
    
    # Invalid BBC non-article URLs (e.g. live, audio, category index)
    assert runner._is_valid_article_url(bbc_source, "https://www.bbc.co.uk/sport/football/live/c98vz9jvg0vo") is False
    assert runner._is_valid_article_url(bbc_source, "https://www.bbc.co.uk/sport/football/premier-league") is False
    assert runner._is_valid_article_url(bbc_source, "https://www.bbc.co.uk/sport/football/av/5829103") is False


@pytest.mark.asyncio
async def test_end_to_end_decoupled_crawl_flow() -> None:
    db = FakeMongoDatabase()
    writer = V2MongoArticleWriter(db)  # type: ignore[arg-type]

    # Step 1: Simulate seeding from RSS
    rss_fixture = ROOT / "tests/fixtures/mock-news/rss/trusted-general.xml"
    runner = _load_crawler_runner()
    
    from footballpulse_crawler_service.discovery.rss import parse_rss
    feed = parse_rss(rss_fixture.read_bytes(), allowed_domains=("trusted-a.test", "trusted-b.test"), max_entries=10)
    
    now = datetime.now(UTC)
    seeded_ids = []
    for entry in feed.entries:
        art_id = writer.seed_metadata(
            url=entry.url,
            source_name="Trusted General Football",
            title=entry.title,
            published_time=now,
            description=entry.description,
            image_url=entry.image_url,
        )
        if art_id:
            seeded_ids.append(art_id)

    assert len(seeded_ids) == len(feed.entries)
    assert db.news_metadata.count_documents({}) == len(feed.entries)
    assert db.news_content.count_documents({}) == 0

    # Step 2: Query unextracted and simulate parallel extraction
    unextracted = writer.get_unextracted_articles()
    assert len(unextracted) == len(seeded_ids)

    processor = ArticleContentProcessor()
    articles_dir = ROOT / "tests/fixtures/mock-news/articles"
    fixture_map = {
        "https://trusted-a.test/football/official-denial": articles_dir / "official-denial.html",
        "https://trusted-a.test/football/vinicius-injury": articles_dir / "injury.html",
        "https://trusted-b.test/football/real-madrid-arsenal": articles_dir / "match.html",
    }

    # Extract 3 articles that have fixtures
    for item in unextracted:
        url = item["url"]
        if url in fixture_map:
            html = fixture_map[url].read_bytes()
            res = processor.process(html, url=url)
            assert res.text is not None
            writer.write_content(
                article_id=item["_id"],
                content_text=res.text,
                extractor="TRAFILATURA",
                extraction_status="SUCCESS",
                title=res.title,
            )

    # Verify 3 documents in news_content
    assert db.news_content.count_documents({}) == 3

    # Verify remaining unextracted is total - 3
    remaining = writer.get_unextracted_articles()
    assert len(remaining) == len(seeded_ids) - 3
