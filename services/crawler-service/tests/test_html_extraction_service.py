from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from footballpulse_crawler_service.discovery.runner import DiscoveryJob
from footballpulse_crawler_service.discovery.security import UrlSafetyPolicy
from footballpulse_crawler_service.extraction.fetcher import HtmlFetcher
from footballpulse_crawler_service.extraction.service import HtmlExtractionService

FIXTURE = (
    Path(__file__).parents[3]
    / "tests"
    / "fixtures"
    / "mock-news"
    / "articles"
    / "official-denial.html"
)


async def _public_resolver(host: str, port: int) -> tuple[str, ...]:
    del host, port
    return ("93.184.216.34",)


@pytest.mark.anyio
async def test_fetches_and_projects_raw_html_to_cleaned_content() -> None:
    raw_html = FIXTURE.read_bytes()

    async def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            headers={"Content-Type": "text/html"},
            content=raw_html,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = HtmlExtractionService(
            fetcher=HtmlFetcher(
                client=client,
                safety_policy=UrlSafetyPolicy(resolver=_public_resolver),
            )
        )
        result = await service.fetch_and_extract(
            DiscoveryJob(
                "official-denial",
                "https://trusted-a.test/football/official-denial",
                ("trusted-a.test",),
            )
        )

    assert result.source_key == "official-denial"
    assert result.raw_html == raw_html
    assert result.final_url == "https://trusted-a.test/football/official-denial"
    assert result.extraction.title == "Real Madrid deny accepting Vinicius bid"
    assert result.extraction.text == (
        "Real Madrid issue official denial Real Madrid said in an official statement that no "
        "offer for Vinícius Júnior has been accepted."
    )
