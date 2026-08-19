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
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID

from bs4 import BeautifulSoup
from confluent_kafka import Producer
from pymongo import MongoClient
from pymongo.database import Database
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "crawler-service" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "event-contracts" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "runtime-config" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "shared" / "src"))

from footballpulse_crawler_service.application.v2_article_pipeline import V2ArticlePipeline
from footballpulse_crawler_service.discovery.fetcher import RssFetcher, create_http_client
from footballpulse_crawler_service.discovery.runner import DiscoveryJob
from footballpulse_crawler_service.discovery.security import UrlSafetyPolicy
from footballpulse_crawler_service.discovery.service import RssDiscovery
from footballpulse_crawler_service.discovery.v2_policy import (
    V2_BOOTSTRAP_FETCH_LIMIT,
    V2_CANDIDATE_LIMIT,
    V2_SCHEDULED_FETCH_LIMIT,
    select_new_candidates,
)
from footballpulse_crawler_service.domain.source import NewSource, SourceType
from footballpulse_crawler_service.extraction.fetcher import HtmlFetcher
from footballpulse_crawler_service.extraction.processor import ArticleContentProcessor
from footballpulse_crawler_service.extraction.service import ExtractedArticle, HtmlExtractionService
from footballpulse_crawler_service.messaging.v2 import V2NewsCrawledPublisher
from footballpulse_crawler_service.persistence.mongo_v2 import V2MongoArticleWriter
from footballpulse_runtime_config import bind_log_context, configure_logging
from footballpulse_runtime_config import log_event as structured_log_event
from footballpulse_shared import canonicalize_news_url


@dataclass(frozen=True, slots=True)
class CatalogSource:
    name: str
    url: str
    source_type: SourceType
    domains: tuple[str, ...]
    enabled_by_default: bool = True


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
        enabled_by_default=False,
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


def select_sources(source_names: list[str] | None) -> list[CatalogSource]:
    """Return explicit sources, or only sources safe for the default production run."""
    if source_names:
        return [item for item in CATALOG if item.name in source_names]
    return [item for item in CATALOG if item.enabled_by_default]


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


def mongo_connection_url() -> str:
    return os.getenv(
        "FOOTBALLPULSE_V2_MONGODB_URL",
        os.getenv(
            "FOOTBALLPULSE_MONGODB_URL",
            "mongodb://127.0.0.1:27117/?replicaSet=rs0&directConnection=true",
        ),
    )



@dataclass(frozen=True, slots=True)
class LocalSourceRecord:
    name: str
    rss_url: str
    allowed_domains: tuple[str, ...]
    source_type: SourceType
    id: UUID


@dataclass(frozen=True, slots=True)
class LocalBatchRecord:
    id: UUID


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
    source_key: str,
    url: str,
    allowed: tuple[str, ...],
) -> ExtractedArticle:
    rendered = await renderer.fetch(url, allowed_domains=allowed)
    extraction = ArticleContentProcessor().process(rendered.content, url=rendered.final_url)
    return ExtractedArticle(
        source_key=source_key,
        requested_url=url,
        final_url=rendered.final_url,
        content_type="text/html",
        etag=None,
        last_modified=None,
        raw_html=rendered.content,
        extraction=extraction,
    )


async def crawl_source(
    item: CatalogSource,
    source,
    batch,
    pipeline: V2ArticlePipeline,
    database: Database[dict[str, object]],
    client,
    safety,
    renderer,
    max_articles,
    candidate_limit: int,
):
    allowed = tuple(source.allowed_domains)
    links: list[tuple[str, str, str | None, datetime | None]] = []
    if item.source_type is SourceType.RSS:
        rss = RssDiscovery(fetcher=RssFetcher(client=client, safety_policy=safety))
        record = await rss.discover(DiscoveryJob(str(source.id), source.rss_url, allowed))
        links = [
            (entry.url, entry.title, entry.guid, entry.published_at)
            for entry in record.feed.entries[:candidate_limit]
        ]
    elif item.source_type is SourceType.SITEMAP:
        for url in await _sitemap_links(item, source, client, safety, candidate_limit):
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
            listing.content, listing.final_url, host, candidate_limit, item
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
                if len(links) >= candidate_limit:
                    break

    if not links:
        raise RuntimeError("source listing contained no usable article URLs")
    candidate_metadata = {
        canonicalize_news_url(url): (rss_title, guid, published_at)
        for url, rss_title, guid, published_at in links
    }
    candidates = select_new_candidates(
        [url for url, *_rest in links],
        exists=lambda article_id: database.news_metadata.find_one({"_id": article_id}, {"_id": 1}) is not None,
        candidate_limit=candidate_limit,
        fetch_limit=max_articles,
    )
    links = [
        (candidate.url, *candidate_metadata[candidate.url])
        for candidate in candidates
        if candidate.url in candidate_metadata
    ]
    if not links:
        log_event("source_skipped_no_new_candidates", source=item.name, batch_id=batch.id)
        return 0, 0, 0
    fetched = failed = 0
    log_event("source_discovered", source=item.name, batch_id=batch.id, count=len(links))
    extractor = HtmlExtractionService(fetcher=HtmlFetcher(client=client, safety_policy=safety))
    for article_number, (url, rss_title, guid, published_at) in enumerate(links, start=1):
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
                    DiscoveryJob(item.name, url, allowed)
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
                    renderer, source_key=item.name, url=url, allowed=allowed
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
                    renderer, source_key=item.name, url=url, allowed=allowed
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
            log_event(
                "article_extraction_completed",
                source=item.name,
                batch_id=batch.id,
                url=url,
                extractor=article.extraction.extractor,
                html_bytes=len(article.raw_html),
                text_chars=len(article.extraction.text or ""),
            )
            article_id = pipeline.persist_and_publish(article)
            if article_id is None:
                failed += 1
                log_event(
                    "article_failed",
                    source=item.name,
                    batch_id=batch.id,
                    url=url,
                    error_type="MongoWriteRejected",
                    error="crawler v2 writer rejected article payload",
                )
                continue
            fetched += 1
            log_event(
                "article_processed",
                source=item.name,
                batch_id=batch.id,
                url=url,
                article_id=article_id,
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
    selected = select_sources(args.source)
    if not selected:
        raise SystemExit("No matching source. Use --list-sources to see catalog names.")
    mongo_url = mongo_connection_url()
    mongo_client: MongoClient[dict[str, object]] = MongoClient(
        mongo_url,
        uuidRepresentation="standard",
    )
    database: Database[dict[str, object]] = mongo_client[
        os.getenv("FOOTBALLPULSE_V2_MONGODB_DB", os.getenv("FOOTBALLPULSE_MONGODB_DB", "footballpulse_v2"))
    ]
    kafka_producer = Producer(
        {
            "bootstrap.servers": os.getenv(
                "FOOTBALLPULSE_V2_KAFKA_BOOTSTRAP_SERVERS",
                "127.0.0.1:19092",
            )
        }
    )
    writer = V2MongoArticleWriter(database)
    safety = UrlSafetyPolicy()
    browser_enabled = os.getenv("FOOTBALLPULSE_BROWSER_FALLBACK", "true").lower() in {
        "1",
        "true",
        "yes",
    }
    needs_browser = any(
        item.name in BROWSER_LISTING_SOURCES or item.name in BROWSER_ARTICLE_SOURCES
        for item in selected
    )
    renderer = BrowserRenderer(safety) if browser_enabled and needs_browser else None
    if renderer is not None:
        await renderer.start()
    started = time.monotonic()
    fetch_limit = (
        V2_BOOTSTRAP_FETCH_LIMIT
        if os.getenv("FOOTBALLPULSE_CRAWL_MODE", "scheduled").casefold() == "bootstrap"
        else V2_SCHEDULED_FETCH_LIMIT
    )
    max_articles = min(args.max_articles, fetch_limit)
    log_event(
        "crawl_run_started",
        source_count=len(selected),
        max_articles_per_source=max_articles,
        browser_fallback=renderer is not None,
    )
    source_semaphore = asyncio.Semaphore(
        int(os.getenv("FOOTBALLPULSE_V2_SOURCE_CONCURRENCY", "4"))
    )

    async def _crawl_single_source(item: CatalogSource) -> None:
        async with source_semaphore:
            pipeline = V2ArticlePipeline(
                mongo=writer,
                kafka=V2NewsCrawledPublisher(kafka_producer, source_name=item.name),
            )
            source = LocalSourceRecord(
                name=item.name,
                rss_url=item.url,
                allowed_domains=item.domains,
                source_type=item.source_type,
                id=uuid.uuid5(uuid.NAMESPACE_URL, item.url),
            )
            batch = LocalBatchRecord(id=uuid.uuid4())
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
                        pipeline,
                        database,
                        client,
                        safety,
                        renderer,
                        max_articles,
                        V2_CANDIDATE_LIMIT,
                    )
                    status = "COMPLETED" if failed == 0 else "PARTIAL"
                except asyncio.CancelledError:
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
                    status = "FAILED"
            log_event(
                "source_completed",
                source=item.name,
                batch_id=batch.id,
                status=status,
                discovered=discovered,
                fetched=fetched,
                failed=failed,
                duration_ms=round((time.monotonic() - source_started) * 1000),
            )

    try:
        async with create_http_client(max_connections=20) as client:
            await asyncio.gather(*(_crawl_single_source(item) for item in selected))
    finally:
        if renderer is not None:
            await renderer.close()
        kafka_producer.flush(10)
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
        "--source",
        action="append",
        help="catalog source name; repeatable; default: enabled sources (Reuters is opt-in)",
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
