from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from footballpulse_crawler_service.discovery.fetcher import UnsupportedContentTypeError
from footballpulse_crawler_service.discovery.security import UrlSafetyPolicy
from footballpulse_crawler_service.extraction.fetcher import HtmlFetcher

FIXTURE = (
    Path(__file__).parents[3] / "tests" / "fixtures" / "mock-news" / "articles" / "vinicius-12.html"
)


async def _public_resolver(host: str, port: int) -> tuple[str, ...]:
    del host, port
    return ("93.184.216.34",)


@pytest.mark.anyio
async def test_fetches_html_with_shared_network_safety_policy() -> None:
    payload = FIXTURE.read_bytes()

    async def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            headers={"Content-Type": "text/html; charset=utf-8"},
            content=payload,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        fetcher = HtmlFetcher(
            client=client,
            safety_policy=UrlSafetyPolicy(resolver=_public_resolver),
        )
        fetched = await fetcher.fetch(
            "https://trusted-a.test/football/vinicius-offer",
            allowed_domains=("trusted-a.test",),
        )

    assert fetched.content == payload
    assert fetched.content_type == "text/html"


@pytest.mark.anyio
async def test_html_fetcher_rejects_non_html_response() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            content=b"{}",
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        fetcher = HtmlFetcher(
            client=client,
            safety_policy=UrlSafetyPolicy(resolver=_public_resolver),
        )
        with pytest.raises(UnsupportedContentTypeError):
            await fetcher.fetch(
                "https://trusted-a.test/football/article",
                allowed_domains=("trusted-a.test",),
            )
