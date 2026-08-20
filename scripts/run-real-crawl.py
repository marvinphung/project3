#!/usr/bin/env python3
"""Run real RSS/sitemap/HTML crawl pipeline in 2 decoupled steps.

Step 1 (Discovery & Seeding):
- Fetches RSS feeds and sitemaps from priority sources in domain-sources-reference.md
- Filters articles published within the last 30 days (and BBC /articles/ constraint)
- Generates deterministic UUID (_id) from canonical URL
- Deduplicates against MongoDB news_metadata and seeds new metadata records

Step 2 (Content Extraction & Parallel Crawl):
- Finds all news_metadata records that do not yet exist in news_content
- Fetches article HTML in parallel with bounded concurrency
- Extracts cleaned text using Trafilatura -> BeautifulSoup -> Playwright fallback
- Stores extracted text into news_content and updates news_metadata.content_hash
- Publishes lightweight pointer to Kafka (news.crawled.v1)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
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

from footballpulse_crawler_service.discovery.fetcher import RssFetcher, create_http_client
from footballpulse_crawler_service.discovery.runner import DiscoveryJob
from footballpulse_crawler_service.discovery.security import UrlSafetyPolicy
from footballpulse_crawler_service.discovery.service import RssDiscovery
from footballpulse_crawler_service.discovery.v2_policy import (
    DEFAULT_MAX_AGE_DAYS,
    V2_BOOTSTRAP_FETCH_LIMIT,
    V2_CANDIDATE_LIMIT,
    V2_SCHEDULED_FETCH_LIMIT,
    is_within_age_limit,
)
from footballpulse_crawler_service.domain.source import SourceType
from footballpulse_crawler_service.extraction.fetcher import HtmlFetcher
from footballpulse_crawler_service.extraction.processor import ArticleContentProcessor
from footballpulse_crawler_service.extraction.service import ExtractedArticle, HtmlExtractionService
from footballpulse_crawler_service.messaging.v2 import V2NewsCrawledPublisher
from footballpulse_crawler_service.persistence.mongo_v2 import V2MongoArticleWriter
from footballpulse_runtime_config import configure_logging
from footballpulse_runtime_config import log_event as structured_log_event


@dataclass(frozen=True, slots=True)
class CatalogSource:
    name: str
    url: str
    source_type: SourceType
    domains: tuple[str, ...]
    enabled_by_default: bool = True
    requires_article_path: bool = False


# Source catalog based on docs/version2/domain-sources-reference.md
CATALOG: tuple[CatalogSource, ...] = (
    # --- Priority RSS/Sitemap Sources (Enabled by default) ---
    # BBC Sport Football (All 8 feeds from reference doc, requires /articles/ path)
    CatalogSource(
        "BBC Sport - Premier League",
        "https://feeds.bbci.co.uk/sport/football/premier-league/rss.xml",
        SourceType.RSS,
        ("bbci.co.uk", "bbc.co.uk", "bbc.com"),
        enabled_by_default=True,
        requires_article_path=True,
    ),
    CatalogSource(
        "BBC Sport - Champions League",
        "https://feeds.bbci.co.uk/sport/football/champions-league/rss.xml",
        SourceType.RSS,
        ("bbci.co.uk", "bbc.co.uk", "bbc.com"),
        enabled_by_default=True,
        requires_article_path=True,
    ),
    CatalogSource(
        "BBC Sport - Europa League",
        "https://feeds.bbci.co.uk/sport/football/europa-league/rss.xml",
        SourceType.RSS,
        ("bbci.co.uk", "bbc.co.uk", "bbc.com"),
        enabled_by_default=True,
        requires_article_path=True,
    ),
    CatalogSource(
        "BBC Sport - FA Cup",
        "https://feeds.bbci.co.uk/sport/football/fa-cup/rss.xml",
        SourceType.RSS,
        ("bbci.co.uk", "bbc.co.uk", "bbc.com"),
        enabled_by_default=True,
        requires_article_path=True,
    ),
    CatalogSource(
        "BBC Sport - League Cup",
        "https://feeds.bbci.co.uk/sport/football/league-cup/rss.xml",
        SourceType.RSS,
        ("bbci.co.uk", "bbc.co.uk", "bbc.com"),
        enabled_by_default=True,
        requires_article_path=True,
    ),
    CatalogSource(
        "BBC Sport - World Cup",
        "https://feeds.bbci.co.uk/sport/football/world-cup/rss.xml",
        SourceType.RSS,
        ("bbci.co.uk", "bbc.co.uk", "bbc.com"),
        enabled_by_default=True,
        requires_article_path=True,
    ),
    CatalogSource(
        "BBC Sport - European",
        "https://feeds.bbci.co.uk/sport/football/european/rss.xml",
        SourceType.RSS,
        ("bbci.co.uk", "bbc.co.uk", "bbc.com"),
        enabled_by_default=True,
        requires_article_path=True,
    ),
    CatalogSource(
        "BBC Sport - Football RSS",
        "https://feeds.bbci.co.uk/sport/football/rss.xml",
        SourceType.RSS,
        ("bbci.co.uk", "bbc.co.uk", "bbc.com"),
        enabled_by_default=True,
        requires_article_path=True,
    ),
    # The Guardian Football
    CatalogSource(
        "The Guardian Football",
        "https://www.theguardian.com/football/rss",
        SourceType.RSS,
        ("theguardian.com",),
        enabled_by_default=True,
    ),
    # The Athletic (NYTimes)
    CatalogSource(
        "The Athletic Football",
        "https://www.nytimes.com/athletic/rss/football/",
        SourceType.RSS,
        ("nytimes.com",),
        enabled_by_default=True,
    ),
    # The Telegraph Football (Sitemap)
    CatalogSource(
        "The Telegraph Football",
        "https://www.telegraph.co.uk/football/sitemap-0.xml",
        SourceType.SITEMAP,
        ("telegraph.co.uk",),
        enabled_by_default=True,
    ),
    # The Independent Football
    CatalogSource(
        "The Independent Football",
        "https://www.independent.co.uk/sport/football/rss",
        SourceType.RSS,
        ("independent.co.uk",),
        enabled_by_default=True,
    ),
    # --- Sources without RSS/Sitemap (Disabled/Opt-in per reference doc) ---
    CatalogSource(
        "Reuters Soccer",
        "https://www.reuters.com/sports/soccer/",
        SourceType.HTML,
        ("reuters.com",),
        enabled_by_default=False,
    ),
    CatalogSource(
        "ESPN Soccer",
        "https://www.espn.com/soccer/",
        SourceType.HTML,
        ("espn.com",),
        enabled_by_default=False,
    ),
    CatalogSource(
        "Sky Sports Football",
        "https://www.skysports.com/football",
        SourceType.HTML,
        ("skysports.com",),
        enabled_by_default=False,
    ),
    CatalogSource(
        "Transfermarkt",
        "https://www.transfermarkt.co.uk/aktuell/newsarchiv",
        SourceType.HTML,
        ("transfermarkt.co.uk",),
        enabled_by_default=False,
    ),
    CatalogSource(
        "Associated Press Soccer",
        "https://apnews.com/hub/soccer",
        SourceType.HTML,
        ("apnews.com",),
        enabled_by_default=False,
    ),
    CatalogSource(
        "Premier League",
        "https://www.premierleague.com/en/news",
        SourceType.HTML,
        ("premierleague.com",),
        enabled_by_default=False,
    ),
    CatalogSource(
        "UEFA News",
        "https://www.uefa.com/news-media/",
        SourceType.HTML,
        ("uefa.com",),
        enabled_by_default=False,
    ),
    CatalogSource(
        "FIFA News",
        "https://www.fifa.com/sitemap",
        SourceType.SITEMAP,
        ("fifa.com",),
        enabled_by_default=False,
    ),
    CatalogSource(
        "FIFA World Cup News",
        "https://www.fifa.com/sitemap?scope=worldcup2026",
        SourceType.SITEMAP,
        ("fifa.com",),
        enabled_by_default=False,
    ),
)

LOGGER = logging.getLogger("footballpulse.crawler")
BROWSER_LISTING_SOURCES = frozenset(
    {"ESPN Soccer", "Transfermarkt", "Reuters Soccer", "Premier League"}
)
BROWSER_ARTICLE_SOURCES = BROWSER_LISTING_SOURCES | frozenset(
    {"The Athletic Football", "The Telegraph Football", "FIFA News", "FIFA World Cup News"}
)


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
    """Render allowlisted public pages that require a real browser."""

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


def _is_valid_article_url(source: CatalogSource, url: str) -> bool:
    """Check if URL matches source-specific article patterns."""
    path = urlsplit(url).path.lower().rstrip("/")
    if source.requires_article_path:
        return "/articles/" in path
    if "bbc" in source.name.lower():
        return "/articles/" in path
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
        if _is_valid_article_url(source, normalized) and normalized not in links:
            links.append(normalized)
        if len(links) >= limit:
            break
    return links


async def _sitemap_entries(
    item: CatalogSource, client, safety: UrlSafetyPolicy, limit: int, max_age_days: int
) -> list[tuple[str, str, datetime | None, str | None, str | None]]:
    """Parse sitemap XML and return list of (url, title, published_at, description, image_url)."""
    fetcher = RssFetcher(client=client, safety_policy=safety, max_response_bytes=10 * 1024 * 1024)
    listing = await fetcher.fetch(item.url, allowed_domains=item.domains)
    soup = BeautifulSoup(listing.content, "lxml-xml")

    # Check for sitemap index
    sitemap_locs = [node.get_text(strip=True) for node in soup.find_all("sitemap")]
    if sitemap_locs:
        results = []
        for sitemap_node in soup.find_all("sitemap")[:10]:
            loc = sitemap_node.find("loc")
            if not loc:
                continue
            child_url = loc.get_text(strip=True)
            try:
                child = await fetcher.fetch(child_url, allowed_domains=item.domains)
                child_soup = BeautifulSoup(child.content, "lxml-xml")
                for url_node in child_soup.find_all("url"):
                    url_loc = url_node.find("loc")
                    if not url_loc:
                        continue
                    url = url_loc.get_text(strip=True)
                    if not _is_valid_article_url(item, url):
                        continue
                    lastmod_node = url_node.find("lastmod")
                    published_at = None
                    if lastmod_node:
                        with suppress(Exception):
                            published_at = datetime.fromisoformat(
                                lastmod_node.get_text(strip=True)
                            ).astimezone(UTC)
                    if not is_within_age_limit(published_at, max_days=max_age_days):
                        continue
                    title = url.rsplit("/", 1)[-1].replace("-", " ")[:500] or url
                    results.append((url, title, published_at, None, None))
                    if len(results) >= limit:
                        return results
            except Exception:
                continue
        return results

    results = []
    for url_node in soup.find_all("url"):
        loc = url_node.find("loc")
        if not loc:
            continue
        url = loc.get_text(strip=True)
        if not _is_valid_article_url(item, url):
            continue
        lastmod_node = url_node.find("lastmod")
        published_at = None
        if lastmod_node:
            with suppress(Exception):
                published_at = datetime.fromisoformat(
                    lastmod_node.get_text(strip=True)
                ).astimezone(UTC)
        if not is_within_age_limit(published_at, max_days=max_age_days):
            continue
        title = url.rsplit("/", 1)[-1].replace("-", " ")[:500] or url
        results.append((url, title, published_at, None, None))
        if len(results) >= limit:
            break
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


# =========================================================================
# STEP 1: Discovery & URL Seeding into news_metadata
# =========================================================================


@dataclass(frozen=True, slots=True)
class DiscoveredCandidate:
    url: str
    title: str
    published_at: datetime | None
    description: str | None
    image_url: str | None
    source_name: str


async def discover_source_entries(
    item: CatalogSource,
    client,
    safety: UrlSafetyPolicy,
    candidate_limit: int,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
) -> list[DiscoveredCandidate]:
    """Fetch RSS or Sitemap and parse entries with 30-day filter and domain constraints."""
    candidates: list[DiscoveredCandidate] = []

    if item.source_type is SourceType.RSS:
        rss = RssDiscovery(
            fetcher=RssFetcher(client=client, safety_policy=safety),
            max_entries_per_feed=candidate_limit,
        )
        job = DiscoveryJob(item.name, item.url, item.domains)
        record = await rss.discover(job)
        for entry in record.feed.entries:
            if not _is_valid_article_url(item, entry.url):
                continue
            if not is_within_age_limit(entry.published_at, max_days=max_age_days):
                continue
            candidates.append(
                DiscoveredCandidate(
                    url=entry.url,
                    title=entry.title,
                    published_at=entry.published_at,
                    description=entry.description,
                    image_url=entry.image_url,
                    source_name=item.name,
                )
            )
    elif item.source_type is SourceType.SITEMAP:
        entries = await _sitemap_entries(item, client, safety, candidate_limit, max_age_days)
        for url, title, published_at, desc, img in entries:
            candidates.append(
                DiscoveredCandidate(
                    url=url,
                    title=title,
                    published_at=published_at,
                    description=desc,
                    image_url=img,
                    source_name=item.name,
                )
            )
    else:
        # Fallback for HTML sources (when explicitly selected)
        listing = await HtmlFetcher(client=client, safety_policy=safety).fetch(
            item.url, allowed_domains=item.domains
        )
        host = urlsplit(item.url).hostname.lower().rstrip(".")
        links = article_links_from_html(
            listing.content, listing.final_url, host, candidate_limit, item
        )
        for url in links:
            candidates.append(
                DiscoveredCandidate(
                    url=url,
                    title=url.rsplit("/", 1)[-1].replace("-", " ")[:500] or url,
                    published_at=None,
                    description=None,
                    image_url=None,
                    source_name=item.name,
                )
            )

    return candidates


async def run_step1_discovery(
    sources: list[CatalogSource],
    writer: V2MongoArticleWriter,
    client,
    safety: UrlSafetyPolicy,
    candidate_limit: int,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
) -> tuple[int, int, int]:
    """Run Step 1: Discover URLs, filter 30-day window, deduplicate and seed news_metadata."""
    log_event("step1_discovery_started", source_count=len(sources), max_age_days=max_age_days)
    total_discovered = 0
    total_existing = 0
    total_seeded = 0

    async def _discover_and_seed(source: CatalogSource) -> None:
        nonlocal total_discovered, total_existing, total_seeded
        try:
            entries = await discover_source_entries(
                source, client, safety, candidate_limit, max_age_days=max_age_days
            )
            discovered_count = len(entries)
            seeded_count = 0
            existing_count = 0
            for candidate in entries:
                article_id = writer.seed_metadata(
                    url=candidate.url,
                    source_name=candidate.source_name,
                    title=candidate.title,
                    published_time=candidate.published_at,
                    description=candidate.description,
                    image_url=candidate.image_url,
                )
                if article_id is not None:
                    seeded_count += 1
                else:
                    existing_count += 1

            total_discovered += discovered_count
            total_existing += existing_count
            total_seeded += seeded_count
            log_event(
                "step1_source_seeded",
                source=source.name,
                discovered=discovered_count,
                seeded=seeded_count,
                existing=existing_count,
            )
        except Exception as exc:
            log_event(
                "step1_source_discovery_failed",
                source=source.name,
                error_type=type(exc).__name__,
                error=str(exc),
            )

    await asyncio.gather(*(_discover_and_seed(s) for s in sources))
    log_event(
        "step1_discovery_completed",
        total_discovered=total_discovered,
        total_seeded=total_seeded,
        total_existing=total_existing,
    )
    return total_discovered, total_existing, total_seeded


# =========================================================================
# STEP 2: Content Extraction & Parallel Crawl into news_content
# =========================================================================


async def extract_and_save_article(
    doc: dict[str, object],
    writer: V2MongoArticleWriter,
    extractor: HtmlExtractionService,
    renderer: BrowserRenderer | None,
    safety: UrlSafetyPolicy,
    kafka_publisher: V2NewsCrawledPublisher | None,
    allowed_domains: tuple[str, ...],
) -> bool:
    """Fetch article content using primary/fallback extractors and persist to news_content."""
    article_id = doc["_id"]
    if not isinstance(article_id, UUID):
        article_id = UUID(str(article_id))

    url = str(doc.get("url") or doc.get("canonical_url", ""))
    source_name = str(doc.get("source_name", "Unknown"))
    if not url:
        return False

    started = time.monotonic()
    try:
        article: ExtractedArticle | None = None
        try:
            article = await extractor.fetch_and_extract(
                DiscoveryJob(source_name, url, allowed_domains)
            )
        except Exception as static_error:
            if renderer is not None and (
                source_name in BROWSER_ARTICLE_SOURCES
                or "nytimes.com" in url
                or "telegraph.co.uk" in url
            ):
                log_event(
                    "step2_browser_fallback",
                    source=source_name,
                    url=url,
                    reason=type(static_error).__name__,
                )
                article = await _browser_article(
                    renderer, source_key=source_name, url=url, allowed=allowed_domains
                )
            else:
                raise

        if (
            article.extraction.status.value == "FAILED"
            and renderer is not None
            and (source_name in BROWSER_ARTICLE_SOURCES or "nytimes.com" in url)
        ):
            article = await _browser_article(
                renderer, source_key=source_name, url=url, allowed=allowed_domains
            )

        if article.extraction.status.value == "FAILED" or not article.extraction.text:
            log_event(
                "step2_article_extraction_failed",
                source=source_name,
                url=url,
                diagnostics=",".join(article.extraction.diagnostics),
            )
            return False

        saved = writer.write_content(
            article_id=article_id,
            content_text=article.extraction.text,
            extractor=article.extraction.extractor.value if article.extraction.extractor else "UNKNOWN",
            extraction_status=article.extraction.status.value,
            title=article.extraction.title,
        )

        if saved and kafka_publisher is not None:
            with suppress(Exception):
                kafka_publisher.publish(article_id=article_id, canonical_url=article.final_url)

        log_event(
            "step2_article_extracted",
            source=source_name,
            article_id=article_id,
            url=url,
            extractor=article.extraction.extractor,
            text_length=len(article.extraction.text),
            duration_ms=round((time.monotonic() - started) * 1000),
        )
        return True
    except Exception as exc:
        log_event(
            "step2_article_error",
            source=source_name,
            article_id=article_id,
            url=url,
            error_type=type(exc).__name__,
            error=str(exc),
        )
        return False


async def run_step2_extraction(
    writer: V2MongoArticleWriter,
    client,
    safety: UrlSafetyPolicy,
    renderer: BrowserRenderer | None,
    kafka_producer: Producer | None,
    max_articles: int,
    concurrency: int = 6,
    source_names: list[str] | None = None,
) -> tuple[int, int, int]:
    """Run Step 2: Query unextracted metadata records and crawl content in parallel."""
    unextracted = writer.get_unextracted_articles(
        limit=max_articles,
        source_names=tuple(source_names) if source_names else None,
    )
    if not unextracted:
        log_event("step2_no_unextracted_articles")
        return 0, 0, 0

    log_event(
        "step2_extraction_started",
        count=len(unextracted),
        concurrency=concurrency,
    )
    extractor = HtmlExtractionService(fetcher=HtmlFetcher(client=client, safety_policy=safety))
    semaphore = asyncio.Semaphore(concurrency)

    source_domain_map = {s.name: s.domains for s in CATALOG}
    default_domains = (
        "bbci.co.uk",
        "bbc.co.uk",
        "bbc.com",
        "theguardian.com",
        "nytimes.com",
        "telegraph.co.uk",
        "independent.co.uk",
    )

    success_count = 0
    fail_count = 0

    async def _extract_worker(doc: dict[str, object]) -> None:
        nonlocal success_count, fail_count
        source_name = str(doc.get("source_name", ""))
        allowed_domains = source_domain_map.get(source_name, default_domains)
        publisher = (
            V2NewsCrawledPublisher(kafka_producer, source_name=source_name)
            if kafka_producer is not None
            else None
        )
        async with semaphore:
            ok = await extract_and_save_article(
                doc=doc,
                writer=writer,
                extractor=extractor,
                renderer=renderer,
                safety=safety,
                kafka_publisher=publisher,
                allowed_domains=allowed_domains,
            )
            if ok:
                success_count += 1
            else:
                fail_count += 1

    await asyncio.gather(*(_extract_worker(doc) for doc in unextracted))
    log_event(
        "step2_extraction_completed",
        total=len(unextracted),
        succeeded=success_count,
        failed=fail_count,
    )
    return len(unextracted), success_count, fail_count


# =========================================================================
# Main Execution Pipeline
# =========================================================================


async def main_async(args: argparse.Namespace) -> int:
    selected = select_sources(args.source)
    if not selected and args.step in {"all", "1", "discovery"}:
        raise SystemExit("No matching source. Use --list-sources to see catalog names.")

    mongo_url = mongo_connection_url()
    mongo_client: MongoClient[dict[str, object]] = MongoClient(
        mongo_url,
        uuidRepresentation="standard",
    )
    database: Database[dict[str, object]] = mongo_client[
        os.getenv(
            "FOOTBALLPULSE_V2_MONGODB_DB",
            os.getenv("FOOTBALLPULSE_MONGODB_DB", "footballpulse_v2"),
        )
    ]

    kafka_producer = None
    try:
        kafka_producer = Producer(
            {
                "bootstrap.servers": os.getenv(
                    "FOOTBALLPULSE_V2_KAFKA_BOOTSTRAP_SERVERS",
                    "127.0.0.1:19092",
                )
            }
        )
    except Exception:
        kafka_producer = None

    writer = V2MongoArticleWriter(database)
    safety = UrlSafetyPolicy()

    browser_enabled = os.getenv("FOOTBALLPULSE_BROWSER_FALLBACK", "true").lower() in {
        "1",
        "true",
        "yes",
    }
    renderer = BrowserRenderer(safety) if browser_enabled else None
    if renderer is not None:
        try:
            await renderer.start()
        except Exception:
            renderer = None

    fetch_limit = (
        V2_BOOTSTRAP_FETCH_LIMIT
        if os.getenv("FOOTBALLPULSE_CRAWL_MODE", "scheduled").casefold() == "bootstrap"
        else V2_SCHEDULED_FETCH_LIMIT
    )
    max_articles = min(args.max_articles, fetch_limit)
    step = getattr(args, "step", "all")
    concurrency = getattr(args, "concurrency", 6)
    max_age_days = getattr(args, "max_age_days", DEFAULT_MAX_AGE_DAYS)

    started = time.monotonic()
    log_event(
        "crawl_pipeline_started",
        step=step,
        source_count=len(selected),
        max_articles=max_articles,
        concurrency=concurrency,
    )

    try:
        async with create_http_client(max_connections=30) as client:
            # Execute Step 1: Discovery & Seeding
            if step in {"all", "1", "discovery"}:
                print("\n=== Running Step 1: Discovery & Metadata Seeding (Last 30 Days) ===")
                disc, exist, seeded = await run_step1_discovery(
                    sources=selected,
                    writer=writer,
                    client=client,
                    safety=safety,
                    candidate_limit=V2_CANDIDATE_LIMIT,
                    max_age_days=max_age_days,
                )
                print(
                    f"Step 1 finished: discovered={disc}, already_in_db={exist}, newly_seeded={seeded}"
                )

            # Execute Step 2: Content Extraction & Parallel Crawling
            if step in {"all", "2", "content"}:
                print("\n=== Running Step 2: Parallel Content Extraction & Storage ===")
                total_req, ok_count, fail_count = await run_step2_extraction(
                    writer=writer,
                    client=client,
                    safety=safety,
                    renderer=renderer,
                    kafka_producer=kafka_producer,
                    max_articles=max_articles * max(1, len(selected)),
                    concurrency=concurrency,
                    source_names=[s.name for s in selected] if args.source else None,
                )
                print(
                    f"Step 2 finished: unextracted_targeted={total_req}, succeeded={ok_count}, failed={fail_count}"
                )

    finally:
        if renderer is not None:
            await renderer.close()
        if kafka_producer is not None:
            kafka_producer.flush(5)
        mongo_client.close()
        log_event(
            "crawl_pipeline_completed",
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
        "--step",
        choices=["all", "1", "2", "discovery", "content"],
        default="all",
        help="Pipeline step to run: '1'/'discovery', '2'/'content', or 'all' (default: all)",
    )
    parser.add_argument(
        "--source",
        action="append",
        help="Catalog source name; repeatable; default: enabled RSS/Sitemap sources",
    )
    parser.add_argument("--max-articles", type=int, default=20)
    parser.add_argument(
        "--concurrency", type=int, default=6, help="Parallel worker concurrency for Step 2"
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=DEFAULT_MAX_AGE_DAYS,
        help="Maximum article age in days from pubDate (default: 30)",
    )
    parser.add_argument("--list-sources", action="store_true")
    args = parser.parse_args()

    if args.list_sources:
        print("=== FootballPulse Crawler Sources ===")
        for item in CATALOG:
            status = "ENABLED" if item.enabled_by_default else "DISABLED (no RSS/Sitemap or opt-in)"
            print(f"[{status}] {item.name} | {item.source_type.value} | {item.url}")
        return 0

    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
