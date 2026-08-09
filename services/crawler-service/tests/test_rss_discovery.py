from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from footballpulse_crawler_service.discovery.fetcher import RssFetcher
from footballpulse_crawler_service.discovery.runner import DiscoveryJob
from footballpulse_crawler_service.discovery.security import UrlSafetyPolicy
from footballpulse_crawler_service.discovery.service import RssDiscovery

FIXTURE = (
    Path(__file__).parents[3] / "tests" / "fixtures" / "mock-news" / "rss" / "trusted-general.xml"
)


async def _public_resolver(host: str, port: int) -> tuple[str, ...]:
    del host, port
    return ("93.184.216.34",)


@pytest.mark.anyio
async def test_discovers_fixture_entries_without_article_content() -> None:
    payload = FIXTURE.read_bytes()

    async def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            headers={"Content-Type": "application/rss+xml"},
            content=payload,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        discovery = RssDiscovery(
            fetcher=RssFetcher(
                client=client,
                safety_policy=UrlSafetyPolicy(resolver=_public_resolver),
            )
        )
        record = await discovery.discover(
            DiscoveryJob(
                "trusted-general",
                "https://trusted-a.test/feed.xml",
                ("trusted-a.test", "trusted-b.test"),
            )
        )

    assert record.source_key == "trusted-general"
    assert len(record.feed.entries) == 6
    assert record.feed.entries[0].guid == "official-denial"
    assert record.feed.entries[0].title == "Real issue denial"
