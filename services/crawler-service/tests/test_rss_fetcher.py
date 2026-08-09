from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import httpx
import pytest
from footballpulse_crawler_service.discovery.fetcher import (
    ResponseLimitError,
    RssFetcher,
    UnsupportedContentTypeError,
)
from footballpulse_crawler_service.discovery.retry import RetryPolicy
from footballpulse_crawler_service.discovery.security import UrlSafetyPolicy


async def _public_resolver(host: str, port: int) -> tuple[str, ...]:
    del host, port
    return ("93.184.216.34",)


def _policy() -> UrlSafetyPolicy:
    return UrlSafetyPolicy(resolver=_public_resolver)


@pytest.mark.anyio
async def test_streams_valid_feed_and_revalidates_redirect() -> None:
    requested: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.path == "/feed":
            return httpx.Response(302, headers={"Location": "/latest.xml"})
        return httpx.Response(
            200,
            headers={"Content-Type": "application/rss+xml"},
            content=b"<rss><channel><item/></channel></rss>",
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        fetcher = RssFetcher(client=client, safety_policy=_policy())
        response = await fetcher.fetch(
            "https://news.example.com/feed",
            allowed_domains=("example.com",),
        )

    assert requested == [
        "https://news.example.com/feed",
        "https://news.example.com/latest.xml",
    ]
    assert response.final_url == "https://news.example.com/latest.xml"
    assert response.content.startswith(b"<rss>")


@pytest.mark.anyio
async def test_rejects_oversized_content_length_before_body() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            headers={"Content-Type": "application/xml", "Content-Length": "200"},
            content=b"x" * 200,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        fetcher = RssFetcher(client=client, safety_policy=_policy(), max_response_bytes=100)
        with pytest.raises(ResponseLimitError):
            await fetcher.fetch(
                "https://news.example.com/feed",
                allowed_domains=("example.com",),
            )


@pytest.mark.anyio
async def test_stops_stream_when_actual_body_crosses_limit() -> None:
    class OversizedStream(httpx.AsyncByteStream):
        async def __aiter__(self) -> AsyncIterator[bytes]:
            yield b"x" * 60
            yield b"y" * 60

    async def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            headers={"Content-Type": "application/xml"},
            stream=OversizedStream(),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        fetcher = RssFetcher(client=client, safety_policy=_policy(), max_response_bytes=100)
        with pytest.raises(ResponseLimitError, match="streamed"):
            await fetcher.fetch(
                "https://news.example.com/feed",
                allowed_domains=("example.com",),
            )


@pytest.mark.anyio
async def test_rejects_non_feed_content_type() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, headers={"Content-Type": "text/html"}, content=b"html")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        fetcher = RssFetcher(client=client, safety_policy=_policy())
        with pytest.raises(UnsupportedContentTypeError):
            await fetcher.fetch(
                "https://news.example.com/feed",
                allowed_domains=("example.com",),
            )


@pytest.mark.anyio
async def test_retries_503_then_succeeds_without_real_sleep() -> None:
    attempts = 0
    delays: list[float] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        del request
        attempts += 1
        if attempts == 1:
            return httpx.Response(503)
        return httpx.Response(
            200,
            headers={"Content-Type": "application/rss+xml"},
            content=b"<rss/>",
        )

    async def sleep(delay: float) -> None:
        delays.append(delay)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        fetcher = RssFetcher(
            client=client,
            safety_policy=_policy(),
            retry_policy=RetryPolicy(max_attempts=2, base_delay_seconds=0.25),
            sleep=sleep,
        )
        await fetcher.fetch(
            "https://news.example.com/feed",
            allowed_domains=("example.com",),
        )

    assert attempts == 2
    assert delays == [0.25]


@pytest.mark.anyio
async def test_cancellation_is_not_converted_to_retry() -> None:
    retries: list[float] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        del request
        raise asyncio.CancelledError

    async def sleep(delay: float) -> None:
        retries.append(delay)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        fetcher = RssFetcher(client=client, safety_policy=_policy(), sleep=sleep)
        with pytest.raises(asyncio.CancelledError):
            await fetcher.fetch(
                "https://news.example.com/feed",
                allowed_domains=("example.com",),
            )

    assert retries == []
