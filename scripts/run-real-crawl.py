#!/usr/bin/env python3
"""Run one real RSS/sitemap/HTML crawl window against the local stores.

This is intentionally a small operational runner until Airflow owns scheduling.
It discovers links from the configured catalog, fetches bounded HTML, writes the
raw/cleaned evidence artifact, and ingests article versions into MongoDB.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
import sys
import time
import uuid
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

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
sys.path.insert(0, str(ROOT / "packages" / "runtime-config" / "src"))

from footballpulse_article_service.application.ingest_article import ArticleIngestionService
from footballpulse_article_service.persistence.mongo_article_store import MongoArticleStore
from footballpulse_article_service.persistence.mongo_indexes import bootstrap_indexes
from footballpulse_crawler_service.application.source_service import (
    CrawlBatchService,
    SourceService,
)
from footballpulse_crawler_service.discovery.fetcher import RssFetcher, create_http_client
from footballpulse_crawler_service.discovery.runner import DiscoveryJob
from footballpulse_crawler_service.discovery.security import UrlSafetyPolicy
from footballpulse_crawler_service.discovery.service import RssDiscovery
from footballpulse_crawler_service.domain.crawl_batch import CrawlBatchStatus
from footballpulse_crawler_service.domain.source import NewSource, SourceType
from footballpulse_crawler_service.extraction.artifact_handoff import ArticleArtifactHandoff
from footballpulse_crawler_service.extraction.fetcher import HtmlFetcher
from footballpulse_crawler_service.extraction.processor import ArticleContentProcessor
from footballpulse_crawler_service.extraction.service import ExtractedArticle, HtmlExtractionService
from footballpulse_crawler_service.persistence.postgres_repositories import (
    PostgresCrawlBatchRepository,
    PostgresSourceRepository,
)
from footballpulse_event_contracts.article import ArticleDiscoveredEvent, ArticleDiscoveredPayload
from footballpulse_fetch_artifacts.filesystem import FilesystemArtifactStore
from footballpulse_runtime_config import bind_log_context, configure_logging
from footballpulse_runtime_config import log_event as structured_log_event


@dataclass(frozen=True, slots=True)
class CatalogSource:
    name: str
    url: str
    source_type: SourceType
    domains: tuple[str, ...]


CATALOG: tuple[CatalogSource, ...] = (
    CatalogSource(
        "BBC Sport Football",
        "https://feeds.bbci.co.uk/sport/football/rss.xml",
        SourceType.RSS,
        ("bbci.co.uk", "bbc.co.uk"),
    ),
    CatalogSource(
        "The Guardian Football",
        "https://www.theguardian.com/football/rss",
        SourceType.RSS,
        ("theguardian.com",),
    ),
    CatalogSource("ESPN Soccer", "https://www.espn.com/soccer/", SourceType.HTML, ("espn.com",)),
    CatalogSource(
        "Transfermarkt",
        "https://www.transfermarkt.co.uk/aktuell/newsarchiv",
        SourceType.HTML,
        ("transfermarkt.co.uk",),
    ),
    CatalogSource(
        "Sky Sports Football Sitemap",
        "https://www.skysports.com/sitemap_news_football.xml",
        SourceType.SITEMAP,
        ("skysports.com",),
    ),
    CatalogSource(
        "Sky Sports Football",
        "https://www.skysports.com/football",
        SourceType.HTML,
        ("skysports.com",),
    ),
    CatalogSource(
        "Reuters Soccer",
        "https://www.reuters.com/sports/soccer/",
        SourceType.HTML,
        ("reuters.com",),
    ),
    CatalogSource(
        "Associated Press Soccer", "https://apnews.com/hub/soccer", SourceType.HTML, ("apnews.com",)
    ),
    CatalogSource(
        "Premier League",
        "https://www.premierleague.com/en/news",
        SourceType.HTML,
        ("premierleague.com",),
    ),
    CatalogSource("UEFA News", "https://www.uefa.com/news-media/", SourceType.HTML, ("uefa.com",)),
    CatalogSource("FIFA News", "https://www.fifa.com/sitemap", SourceType.SITEMAP, ("fifa.com",)),
    CatalogSource(
        "FIFA World Cup News",
        "https://www.fifa.com/sitemap?scope=worldcup2026",
        SourceType.SITEMAP,
        ("fifa.com",),
    ),
)

LOGGER = logging.getLogger("footballpulse.crawler")
BROWSER_LISTING_SOURCES = frozenset(
    {"ESPN Soccer", "Transfermarkt", "Reuters Soccer", "Premier League"}
)
BROWSER_ARTICLE_SOURCES = BROWSER_LISTING_SOURCES | frozenset({"FIFA News", "FIFA World Cup News"})


@dataclass(frozen=True, slots=True)
class RenderedPage:
    requested_url: str
    final_url: str
    content: bytes
    status_code: int
    related_urls: tuple[str, ...] = ()


class BrowserRenderer:
    """Render only allowlisted public pages that require a real browser."""

    def __init__(self, safety_policy: UrlSafetyPolicy) -> None:
        self._safety_policy = safety_policy
        self._playwright = None
        self._browser = None
        self._context = None

    async def start(self) -> None:
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage"],
        )
        self._context = await self._browser.new_context(
            locale="en-GB",
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
            ),
        )

    async def close(self) -> None:
        if self._context is not None:
            await self._context.close()
        if self._browser is not None:
            await self._browser.close()
        if self._playwright is not None:
            await self._playwright.stop()

    async def fetch(
        self,
        url: str,
        *,
        allowed_domains: tuple[str, ...],
        expand_listing: bool = False,
    ) -> RenderedPage:
        if self._context is None:
            raise RuntimeError("browser renderer has not been started")
        validated = await self._safety_policy.validate(url, allowed_domains=allowed_domains)
        page = await self._context.new_page()
        related_urls: list[str] = []
        if expand_listing:
            page.on(
                "response",
                lambda response: (
                    related_urls.append(response.url)
                    if "api.premierleague.com/content/premierleague/text/en/"
                    in response.url.lower()
                    else None
                ),
            )
        try:
            response = await page.goto(validated.url, wait_until="domcontentloaded", timeout=45_000)
            if "/articles/" in urlsplit(validated.url).path.lower():
                with suppress(Exception):
                    await page.wait_for_selector("article", timeout=15_000)
            else:
                with suppress(Exception):
                    await page.wait_for_function(
                        "document.documentElement.outerHTML.length > 50000",
                        timeout=15_000,
                    )
            if expand_listing:
                for _ in range(4):
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await page.wait_for_timeout(750)
            final = await self._safety_policy.validate(page.url, allowed_domains=allowed_domains)
            status_code = response.status if response is not None else 200
            if status_code >= 400:
                raise RuntimeError(f"browser returned HTTP {status_code}")
            content = (await page.content()).encode("utf-8")
            log_event(
                "browser_rendered",
                requested_url=url,
                final_url=final.url,
                status_code=status_code,
                content_length=len(content),
            )
            return RenderedPage(
                url, final.url, content, status_code, tuple(dict.fromkeys(related_urls))
            )
        finally:
            await page.close()


def log_event(event: str, **fields: object) -> None:
    structured_log_event(LOGGER, event, **fields)


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
    existing = next(
        (source for source in service.list_sources(limit=200) if source.rss_url == item.url), None
    )
    if existing is not None:
        if (
            tuple(item.domains) != existing.allowed_domains
            or existing.source_type is not item.source_type
        ):
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
    if source.name == "ESPN Soccer":
        return "/soccer/story/_/id/" in path
    if source.name == "Transfermarkt":
        return "/view/news/" in path
    if source.name == "Reuters Soccer":
        return path.startswith("/sports/soccer/") and path != "/sports/soccer"
    if source.name == "Premier League":
        return path.startswith("/en/news/") and path != "/en/news"
    if source.name == "Sky Sports Football":
        return path.startswith("/football/news/") or path.startswith("/football/live-blog/")
    if source.name == "Associated Press Soccer":
        return path.startswith("/article/")
    if source.name == "FIFA News":
        return "/news/" in path and "/tournaments/mens/worldcup/canadamexicousa2026/" not in path
    if source.name == "FIFA World Cup News":
        return "/tournaments/mens/worldcup/canadamexicousa2026/" in path and "/articles/" in path
    return True


def article_links_from_html(
    payload: bytes, base_url: str, domain: str, limit: int, source: CatalogSource
) -> list[str]:
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
    for child_url in child_urls[:100]:
        child = await fetcher.fetch(child_url, allowed_domains=tuple(source.allowed_domains))
        for url in article_links_from_html(child.content, child.final_url, "fifa.com", limit, item):
            if url not in results:
                results.append(url)
            if len(results) >= limit:
                return results
    return results


async def _browser_article(
    renderer: BrowserRenderer,
    *,
    batch_id: UUID,
    url: str,
    allowed: tuple[str, ...],
) -> ExtractedArticle:
    rendered = await renderer.fetch(url, allowed_domains=allowed)
    extraction = ArticleContentProcessor().process(rendered.content, url=rendered.final_url)
    return ExtractedArticle(
        source_key=str(batch_id),
        requested_url=url,
        final_url=rendered.final_url,
        content_type="text/html",
        etag=None,
        last_modified=None,
        raw_html=rendered.content,
        extraction=extraction,
    )


async def crawl_source(
    item: CatalogSource, source, batch, ingestion, handoff, client, safety, renderer, max_articles
):
    allowed = tuple(source.allowed_domains)
    links: list[tuple[str, str, str | None, datetime | None]] = []
    if item.source_type is SourceType.RSS:
        rss = RssDiscovery(fetcher=RssFetcher(client=client, safety_policy=safety))
        record = await rss.discover(DiscoveryJob(str(source.id), source.rss_url, allowed))
        links = [
            (entry.url, entry.title, entry.guid, entry.published_at)
            for entry in record.feed.entries[:max_articles]
        ]
    elif item.source_type is SourceType.SITEMAP:
        for url in await _sitemap_links(item, source, client, safety, max_articles):
            links.append((url, url.rsplit("/", 1)[-1].replace("-", " ")[:500] or url, None, None))
    else:
        if renderer is not None and item.name in BROWSER_LISTING_SOURCES:
            listing = await renderer.fetch(
                source.rss_url, allowed_domains=allowed, expand_listing=True
            )
        else:
            listing = await HtmlFetcher(client=client, safety_policy=safety).fetch(
                source.rss_url, allowed_domains=allowed
            )
        host = urlsplit(source.rss_url).hostname.lower().rstrip(".")
        for url in article_links_from_html(
            listing.content, listing.final_url, host, max_articles, item
        ):
            links.append((url, url.rsplit("/", 1)[-1].replace("-", " ")[:500] or url, None, None))
        if item.name == "Premier League":
            # DOM also contains a small set of stale promotional links. The
            # content API responses are the authoritative current listing.
            links.clear()
            for api_url in listing.related_urls:
                match = re.search(r"/TEXT/en/(\d+)", api_url, re.IGNORECASE)
                if match is None:
                    continue
                url = f"https://www.premierleague.com/en/news/{match.group(1)}"
                if all(existing[0] != url for existing in links):
                    links.append((url, f"Premier League article {match.group(1)}", None, None))
                if len(links) >= max_articles:
                    break

    if not links:
        raise RuntimeError("source listing contained no usable article URLs")
    fetched = failed = 0
    log_event("source_discovered", source=item.name, batch_id=batch.id, count=len(links))
    extractor = HtmlExtractionService(fetcher=HtmlFetcher(client=client, safety_policy=safety))
    for article_number, (url, rss_title, guid, published_at) in enumerate(links, start=1):
        artifact_id = uuid.uuid4()
        article_started = time.monotonic()
        log_event(
            "article_fetch_started",
            source=item.name,
            batch_id=batch.id,
            article_number=article_number,
            article_total=len(links),
            url=url,
        )
        try:
            try:
                article = await extractor.fetch_and_extract(
                    DiscoveryJob(str(batch.id), url, allowed)
                )
            except Exception as static_error:
                if renderer is None or item.name not in BROWSER_ARTICLE_SOURCES:
                    raise
                log_event(
                    "browser_fallback",
                    source=item.name,
                    url=url,
                    reason_type=type(static_error).__name__,
                    reason=str(static_error),
                )
                article = await _browser_article(
                    renderer, batch_id=batch.id, url=url, allowed=allowed
                )
            if (
                article.extraction.status.value == "FAILED"
                and renderer is not None
                and item.name in BROWSER_ARTICLE_SOURCES
            ):
                log_event(
                    "browser_fallback", source=item.name, url=url, reason_type="ExtractionFailed"
                )
                article = await _browser_article(
                    renderer, batch_id=batch.id, url=url, allowed=allowed
                )
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
            log_event(
                "article_extraction_completed",
                source=item.name,
                batch_id=batch.id,
                url=url,
                extractor=article.extraction.extractor,
                html_bytes=len(article.raw_html),
                text_chars=len(article.extraction.text or ""),
            )
            now = datetime.now(UTC)
            event = ArticleDiscoveredEvent(
                event_id=uuid.uuid4(),
                event_type="article.discovered",
                event_version=1,
                occurred_at=now,
                producer="crawler-service",
                correlation_id=batch.id,
                causation_id=None,
                aggregate_type="source_article",
                aggregate_id=uuid.uuid5(uuid.NAMESPACE_URL, article.final_url),
                idempotency_key=f"{batch.id}:{article.final_url}",
                payload=ArticleDiscoveredPayload(
                    source_id=source.id,
                    batch_id=batch.id,
                    canonical_url=article.final_url,
                    rss_guid=guid,
                    rss_title=rss_title,
                    rss_published_at=published_at,
                    fetched_at=now,
                    fetch_artifact_id=artifact_id,
                    http_status=200,
                    content_type=article.content_type,
                    content_length=len(article.raw_html),
                ),
            )
            ingestion.handle(event)
            fetched += 1
            log_event(
                "article_processed",
                source=item.name,
                batch_id=batch.id,
                url=url,
                status="SUCCESS",
                duration_ms=round((time.monotonic() - article_started) * 1000),
            )
        except Exception as exc:
            failed += 1
            log_event(
                "article_failed",
                source=item.name,
                batch_id=batch.id,
                url=url,
                error_type=type(exc).__name__,
                error=str(exc),
                duration_ms=round((time.monotonic() - article_started) * 1000),
            )
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
    database: Database[dict[str, object]] = mongo_client[
        os.getenv("FOOTBALLPULSE_MONGODB_DB", "footballpulse")
    ]
    bootstrap_indexes(database)
    article_store = MongoArticleStore(database)
    artifact_root = ROOT / os.getenv(
        "FOOTBALLPULSE_FETCH_ARTIFACT_ROOT", ".local-data/fetch-artifacts"
    )
    artifact_store = FilesystemArtifactStore(artifact_root)
    handoff = ArticleArtifactHandoff(store=artifact_store)
    ingestion = ArticleIngestionService(
        repository=article_store, artifacts=artifact_store, clock=lambda: datetime.now(UTC)
    )
    safety = UrlSafetyPolicy()
    renderer = (
        BrowserRenderer(safety)
        if os.getenv("FOOTBALLPULSE_BROWSER_FALLBACK", "true").lower() in {"1", "true", "yes"}
        else None
    )
    if renderer is not None:
        await renderer.start()
    started = time.monotonic()
    log_event(
        "crawl_run_started",
        source_count=len(selected),
        max_articles_per_source=args.max_articles,
        browser_fallback=renderer is not None,
    )
    try:
        async with create_http_client(max_connections=20) as client:
            for item in selected:
                source = ensure_source(source_service, item)
                batch = batch_service.open(
                    source_id=source.id,
                    idempotency_key=f"real:{item.name}:{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}:{uuid.uuid4().hex[:8]}",
                    window_started_at=datetime.now(UTC),
                )
                log_event(
                    "source_started",
                    source=item.name,
                    url=item.url,
                    source_id=source.id,
                    batch_id=batch.id,
                )
                discovered = fetched = failed = 0
                source_started = time.monotonic()
                with bind_log_context(correlation_id=str(batch.id), batch_id=str(batch.id)):
                    try:
                        discovered, fetched, failed = await crawl_source(
                            item,
                            source,
                            batch,
                            ingestion,
                            handoff,
                            client,
                            safety,
                            renderer,
                            args.max_articles,
                        )
                        status = (
                            CrawlBatchStatus.COMPLETED
                            if failed == 0
                            else CrawlBatchStatus.PARTIAL
                        )
                    except asyncio.CancelledError:
                        batch_service.complete(
                            batch.id,
                            status=CrawlBatchStatus.PARTIAL,
                            discovered_count=discovered,
                            fetched_count=fetched,
                            failed_count=failed,
                        )
                        log_event("source_aborted", source=item.name, batch_id=batch.id)
                        raise
                    except Exception as exc:
                        discovered = 1
                        failed = 1
                        log_event(
                            "source_failed",
                            source=item.name,
                            batch_id=batch.id,
                            error_type=type(exc).__name__,
                            error=str(exc),
                        )
                        status = CrawlBatchStatus.FAILED
                batch_service.complete(
                    batch.id,
                    status=status,
                    discovered_count=discovered,
                    fetched_count=fetched,
                    failed_count=failed,
                )
                log_event(
                    "source_completed",
                    source=item.name,
                    batch_id=batch.id,
                    status=status.value,
                    discovered=discovered,
                    fetched=fetched,
                    failed=failed,
                    duration_ms=round((time.monotonic() - source_started) * 1000),
                )
    finally:
        if renderer is not None:
            await renderer.close()
        mongo_client.close()
        log_event(
            "crawl_run_completed",
            source_count=len(selected),
            duration_ms=round((time.monotonic() - started) * 1000),
        )
    return 0


def main() -> int:
    configure_logging(
        service="crawler-worker",
        level=os.getenv("FOOTBALLPULSE_LOG_LEVEL", "INFO"),
        force=True,
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", action="append", help="catalog source name; repeatable; default: all"
    )
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
