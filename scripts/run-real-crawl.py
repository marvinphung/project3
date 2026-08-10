#!/usr/bin/env python3
"""Run one real RSS/sitemap/HTML crawl window against the local stores.

This is intentionally a small operational runner until Airflow owns scheduling.
It discovers links from the configured catalog, fetches bounded HTML, writes the
raw/cleaned evidence artifact, and ingests article versions into MongoDB.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from bs4 import BeautifulSoup
from pymongo import MongoClient
from pymongo.database import Database
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "crawler-service" / "src"))
sys.path.insert(0, str(ROOT / "services" / "article-service" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "fetch-artifacts" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "event-contracts" / "src"))

from footballpulse_article_service.application.ingest_article import ArticleIngestionService
from footballpulse_article_service.persistence.mongo_article_store import MongoArticleStore
from footballpulse_article_service.persistence.mongo_indexes import bootstrap_indexes
from footballpulse_crawler_service.application.source_service import (
    CrawlBatchService,
    SourceService,
)
from footballpulse_crawler_service.discovery.fetcher import RssFetcher, create_http_client
from footballpulse_crawler_service.discovery.rss import parse_rss
from footballpulse_crawler_service.discovery.service import RssDiscovery
from footballpulse_crawler_service.discovery.runner import DiscoveryJob
from footballpulse_crawler_service.discovery.security import UrlSafetyPolicy
from footballpulse_crawler_service.domain.crawl_batch import CrawlBatchStatus
from footballpulse_crawler_service.domain.source import NewSource, SourceType
from footballpulse_crawler_service.extraction.artifact_handoff import ArticleArtifactHandoff
from footballpulse_crawler_service.extraction.fetcher import HtmlFetcher
from footballpulse_crawler_service.extraction.service import HtmlExtractionService
from footballpulse_crawler_service.persistence.postgres_repositories import (
    PostgresCrawlBatchRepository,
    PostgresSourceRepository,
)
from footballpulse_event_contracts.article import ArticleDiscoveredEvent, ArticleDiscoveredPayload
from footballpulse_fetch_artifacts.filesystem import FilesystemArtifactStore


@dataclass(frozen=True, slots=True)
class CatalogSource:
    name: str
    url: str
    source_type: SourceType
    domains: tuple[str, ...]


CATALOG: tuple[CatalogSource, ...] = (
    CatalogSource("BBC Sport Football", "https://feeds.bbci.co.uk/sport/football/rss.xml", SourceType.RSS, ("bbci.co.uk", "bbc.co.uk")),
    CatalogSource("The Guardian Football", "https://www.theguardian.com/football/rss", SourceType.RSS, ("theguardian.com",)),
    CatalogSource("ESPN Soccer", "https://www.espn.com/espn/rss/soccer/news", SourceType.RSS, ("espn.com",)),
    CatalogSource("Transfermarkt", "https://www.transfermarkt.co.uk/rss/news", SourceType.RSS, ("transfermarkt.co.uk",)),
    CatalogSource("Sky Sports Football Sitemap", "https://www.skysports.com/sitemap_news_football.xml", SourceType.SITEMAP, ("skysports.com",)),
    CatalogSource("Sky Sports Football", "https://www.skysports.com/football", SourceType.HTML, ("skysports.com",)),
    CatalogSource("Reuters Soccer", "https://www.reuters.com/sports/soccer/", SourceType.HTML, ("reuters.com",)),
    CatalogSource("Associated Press Soccer", "https://apnews.com/hub/soccer", SourceType.HTML, ("apnews.com",)),
    CatalogSource("Premier League", "https://www.premierleague.com/en/news", SourceType.HTML, ("premierleague.com",)),
    CatalogSource("UEFA News", "https://www.uefa.com/news-media/", SourceType.HTML, ("uefa.com",)),
    CatalogSource("FIFA News", "https://www.fifa.com/sitemap", SourceType.SITEMAP, ("fifa.com",)),
    CatalogSource("FIFA World Cup News", "https://www.fifa.com/sitemap?scope=worldcup2026", SourceType.SITEMAP, ("fifa.com",)),
)

LOGGER = logging.getLogger("footballpulse.crawler")


def log_event(event: str, **fields: object) -> None:
    LOGGER.info(json.dumps({"event": event, **fields}, ensure_ascii=False, default=str))


def database_engine() -> object:
    return create_engine(
        URL.create(
            "postgresql+psycopg",
            username=os.getenv("FOOTBALLPULSE_POSTGRES_USER", "footballpulse"),
            password=os.getenv("FOOTBALLPULSE_POSTGRES_PASSWORD", "footballpulse_local_only"),
            host=os.getenv("FOOTBALLPULSE_POSTGRES_HOST", "127.0.0.1"),
            port=int(os.getenv("FOOTBALLPULSE_POSTGRES_PORT", "5432")),
            database=os.getenv("FOOTBALLPULSE_POSTGRES_DB", "footballpulse"),
        )
    )


def ensure_source(service: SourceService, item: CatalogSource):
    existing = next((source for source in service.list_sources(limit=200) if source.rss_url == item.url), None)
    if existing is not None:
        if tuple(item.domains) != existing.allowed_domains or existing.source_type is not item.source_type:
            return service.update(
                existing.id,
                NewSource.create(
                    name=item.name,
                    rss_url=item.url,
                    allowed_domains=list(item.domains),
                    source_type=item.source_type,
                    reliability_tier=existing.reliability_tier,
                    crawl_interval_minutes=existing.crawl_interval_minutes,
                    max_concurrency=existing.max_concurrency,
                ),
                expected_version=existing.version,
            )
        return existing
    return service.create(
        NewSource.create(
            name=item.name,
            rss_url=item.url,
            allowed_domains=list(item.domains),
            source_type=item.source_type,
            reliability_tier=1 if "Reuters" in item.name or "Associated" in item.name else 2,
            crawl_interval_minutes=360,
            max_concurrency=2,
        )
    )


def _is_article_url(source: CatalogSource, url: str) -> bool:
    path = urlsplit(url).path.lower().rstrip("/")
    if source.name == "Premier League":
        return path.startswith("/en/news/") and path != "/en/news"
    if source.name == "Sky Sports Football":
        return path.startswith("/football/news/") or path.startswith("/football/live-blog/")
    if source.name == "Associated Press Soccer":
        return path.startswith("/article/")
    if source.name == "FIFA News":
        return "/news/" in path and "/tournaments/mens/worldcup/canadamexicousa2026/" not in path
    if source.name == "FIFA World Cup News":
        return "/tournaments/mens/worldcup/canadamexicousa2026/" in path and "/news/" in path
    return True


def article_links_from_html(payload: bytes, base_url: str, domain: str, limit: int, source: CatalogSource) -> list[str]:
    soup = BeautifulSoup(payload, "lxml-xml" if payload.lstrip().startswith(b"<?xml") else "lxml")
    links: list[str] = []
    for element in soup.find_all("loc") + soup.find_all("a", href=True):
        value = element.get_text(strip=True) if element.name == "loc" else element.get("href")
        if not isinstance(value, str):
            continue
        if element.name == "a" and value.startswith("/"):
            value = f"{urlsplit(base_url).scheme}://{urlsplit(base_url).netloc}{value}"
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
            continue
        host = parsed.hostname.lower().rstrip(".")
        if not (host == domain or host.endswith(f".{domain}")):
            continue
        normalized = value.split("#", 1)[0]
        if _is_article_url(source, normalized) and normalized not in links:
            links.append(normalized)
        if len(links) >= limit:
            break
    return links


async def _sitemap_links(item: CatalogSource, source, client, safety, limit: int) -> list[str]:
    fetcher = RssFetcher(client=client, safety_policy=safety, max_response_bytes=5 * 1024 * 1024)
    listing = await fetcher.fetch(source.rss_url, allowed_domains=tuple(source.allowed_domains))
    host = urlsplit(source.rss_url).hostname.lower().rstrip(".")
    direct = article_links_from_html(listing.content, listing.final_url, host, limit, item)
    if direct:
        return direct
    soup = BeautifulSoup(listing.content, "lxml-xml")
    child_urls = [node.get_text(strip=True) for node in soup.find_all("loc")]
    results: list[str] = []
    for child_url in child_urls[:20]:
        child = await fetcher.fetch(child_url, allowed_domains=tuple(source.allowed_domains))
        for url in article_links_from_html(child.content, child.final_url, "fifa.com", limit, item):
            if url not in results:
                results.append(url)
            if len(results) >= limit:
                return results
    return results


async def crawl_source(item: CatalogSource, source, batch, ingestion, handoff, client, safety, max_articles):
    allowed = tuple(source.allowed_domains)
    links: list[tuple[str, str, str | None, datetime | None]] = []
    if item.source_type is SourceType.RSS:
        rss = RssDiscovery(fetcher=RssFetcher(client=client, safety_policy=safety))
        record = await rss.discover(DiscoveryJob(str(source.id), source.rss_url, allowed))
        links = [(entry.url, entry.title, entry.guid, entry.published_at) for entry in record.feed.entries[:max_articles]]
    elif item.source_type is SourceType.SITEMAP:
        for url in await _sitemap_links(item, source, client, safety, max_articles):
            links.append((url, url.rsplit("/", 1)[-1].replace("-", " ")[:500] or url, None, None))
    else:
        fetcher = HtmlFetcher(client=client, safety_policy=safety)
        listing = await fetcher.fetch(source.rss_url, allowed_domains=allowed)
        host = urlsplit(source.rss_url).hostname.lower().rstrip(".")
        for url in article_links_from_html(listing.content, listing.final_url, host, max_articles, item):
            links.append((url, url.rsplit("/", 1)[-1].replace("-", " ")[:500] or url, None, None))

    if not links:
        raise RuntimeError("source listing contained no usable article URLs")
    fetched = failed = 0
    log_event("source_discovered", source=item.name, batch_id=batch.id, count=len(links))
    extractor = HtmlExtractionService(fetcher=HtmlFetcher(client=client, safety_policy=safety))
    for url, rss_title, guid, published_at in links:
        artifact_id = uuid.uuid4()
        try:
            article = await extractor.fetch_and_extract(DiscoveryJob(str(batch.id), url, allowed))
            if article.extraction.status.value == "FAILED":
                failed += 1
                log_event(
                    "article_failed",
                    source=item.name,
                    batch_id=batch.id,
                    url=url,
                    error_type="ExtractionFailed",
                    error=",".join(article.extraction.diagnostics),
                )
                continue
            if article.extraction.title is None:
                article = replace(article, extraction=replace(article.extraction, title=rss_title))
            handoff.persist(artifact_id, article)
            now = datetime.now(UTC)
            event = ArticleDiscoveredEvent(
                event_id=uuid.uuid4(), event_type="article.discovered", event_version=1,
                occurred_at=now, producer="crawler-service", correlation_id=batch.id,
                causation_id=None, aggregate_type="source_article", aggregate_id=uuid.uuid5(uuid.NAMESPACE_URL, article.final_url),
                idempotency_key=f"{batch.id}:{article.final_url}",
                payload=ArticleDiscoveredPayload(
                    source_id=source.id, batch_id=batch.id, canonical_url=article.final_url,
                    rss_guid=guid, rss_title=rss_title, rss_published_at=published_at,
                    fetched_at=now, fetch_artifact_id=artifact_id, http_status=200,
                    content_type=article.content_type, content_length=len(article.raw_html),
                ),
            )
            ingestion.handle(event)
            fetched += 1
            log_event("article_processed", source=item.name, batch_id=batch.id, url=url, status="SUCCESS")
        except Exception as exc:
            failed += 1
            log_event("article_failed", source=item.name, batch_id=batch.id, url=url, error_type=type(exc).__name__, error=str(exc))
    return len(links), fetched, failed


async def main_async(args: argparse.Namespace) -> int:
    selected = [item for item in CATALOG if not args.source or item.name in args.source]
    if not selected:
        raise SystemExit("No matching source. Use --list-sources to see catalog names.")
    engine = database_engine()
    source_repo = PostgresSourceRepository(engine)
    batch_repo = PostgresCrawlBatchRepository(engine)
    source_service = SourceService(source_repo, clock=lambda: datetime.now(UTC))
    batch_service = CrawlBatchService(source_repo, batch_repo, clock=lambda: datetime.now(UTC))
    mongo_url = os.getenv("FOOTBALLPULSE_MONGODB_URL", "mongodb://127.0.0.1:27017/?replicaSet=rs0")
    mongo_client: MongoClient[dict[str, object]] = MongoClient(mongo_url)
    database: Database[dict[str, object]] = mongo_client[os.getenv("FOOTBALLPULSE_MONGODB_DB", "footballpulse")]
    bootstrap_indexes(database)
    article_store = MongoArticleStore(database)
    artifact_root = ROOT / os.getenv("FOOTBALLPULSE_FETCH_ARTIFACT_ROOT", ".local-data/fetch-artifacts")
    artifact_store = FilesystemArtifactStore(artifact_root)
    handoff = ArticleArtifactHandoff(store=artifact_store)
    ingestion = ArticleIngestionService(repository=article_store, artifacts=artifact_store, clock=lambda: datetime.now(UTC))
    safety = UrlSafetyPolicy()
    async with create_http_client(max_connections=20) as client:
        for item in selected:
            source = ensure_source(source_service, item)
            batch = batch_service.open(
                source_id=source.id,
                idempotency_key=f"real:{item.name}:{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}:{uuid.uuid4().hex[:8]}",
                window_started_at=datetime.now(UTC),
            )
            log_event("source_started", source=item.name, url=item.url, source_id=source.id, batch_id=batch.id)
            discovered = fetched = failed = 0
            try:
                discovered, fetched, failed = await crawl_source(item, source, batch, ingestion, handoff, client, safety, args.max_articles)
                status = CrawlBatchStatus.COMPLETED if failed == 0 else CrawlBatchStatus.PARTIAL
            except asyncio.CancelledError:
                batch_service.complete(batch.id, status=CrawlBatchStatus.PARTIAL, discovered_count=discovered, fetched_count=fetched, failed_count=failed)
                log_event("source_aborted", source=item.name, batch_id=batch.id)
                raise
            except Exception as exc:
                discovered = 1
                failed = 1
                log_event("source_failed", source=item.name, batch_id=batch.id, error_type=type(exc).__name__, error=str(exc))
                status = CrawlBatchStatus.FAILED
            batch_service.complete(batch.id, status=status, discovered_count=discovered, fetched_count=fetched, failed_count=failed)
            log_event("source_completed", source=item.name, batch_id=batch.id, status=status.value, discovered=discovered, fetched=fetched, failed=failed)
    mongo_client.close()
    return 0


def main() -> int:
    logging.basicConfig(level=os.getenv("FOOTBALLPULSE_LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", help="catalog source name; repeatable; default: all")
    parser.add_argument("--max-articles", type=int, default=10)
    parser.add_argument("--list-sources", action="store_true")
    args = parser.parse_args()
    if args.list_sources:
        for item in CATALOG:
            print(f"{item.name}\t{item.source_type.value}\t{item.url}")
        return 0
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
