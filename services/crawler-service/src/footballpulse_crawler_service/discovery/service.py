from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from footballpulse_runtime_config import log_event

from footballpulse_crawler_service.discovery.fetcher import RssFetcher
from footballpulse_crawler_service.discovery.rss import ParsedRss, parse_rss
from footballpulse_crawler_service.discovery.runner import DiscoveryJob

LOGGER = logging.getLogger("footballpulse.crawler.discovery")


@dataclass(frozen=True, slots=True)
class RssDiscoveryRecord:
    source_key: str
    fetched_url: str
    feed: ParsedRss


class RssDiscovery:
    def __init__(self, *, fetcher: RssFetcher, max_entries_per_feed: int = 200) -> None:
        if max_entries_per_feed < 1:
            raise ValueError("max_entries_per_feed must be positive")
        self._fetcher = fetcher
        self._max_entries = max_entries_per_feed

    async def discover(self, job: DiscoveryJob) -> RssDiscoveryRecord:
        started = time.monotonic()
        log_event(LOGGER, "feed_fetch_started", source_key=job.key, url=job.url)
        try:
            fetched = await self._fetcher.fetch(
                job.url,
                allowed_domains=job.allowed_domains,
            )
            feed = parse_rss(
                fetched.content,
                allowed_domains=job.allowed_domains,
                max_entries=self._max_entries,
            )
        except Exception as error:
            log_event(
                LOGGER,
                "source_discovery_failed",
                level=logging.ERROR,
                error=error,
                source_key=job.key,
                url=job.url,
                duration_ms=round((time.monotonic() - started) * 1000),
            )
            raise
        log_event(
            LOGGER,
            "source_discovery_completed",
            source_key=job.key,
            final_url=fetched.final_url,
            entry_count=len(feed.entries),
            response_bytes=len(fetched.content),
            duration_ms=round((time.monotonic() - started) * 1000),
        )
        return RssDiscoveryRecord(job.key, fetched.final_url, feed)
