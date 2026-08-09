from __future__ import annotations

from dataclasses import dataclass

from footballpulse_crawler_service.discovery.fetcher import RssFetcher
from footballpulse_crawler_service.discovery.rss import ParsedRss, parse_rss
from footballpulse_crawler_service.discovery.runner import DiscoveryJob


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
        fetched = await self._fetcher.fetch(
            job.url,
            allowed_domains=job.allowed_domains,
        )
        feed = parse_rss(
            fetched.content,
            allowed_domains=job.allowed_domains,
            max_entries=self._max_entries,
        )
        return RssDiscoveryRecord(job.key, fetched.final_url, feed)
