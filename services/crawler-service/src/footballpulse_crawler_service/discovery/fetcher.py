from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx

from footballpulse_crawler_service.discovery.retry import RetryPolicy
from footballpulse_crawler_service.discovery.security import UrlSafetyPolicy

Sleep = Callable[[float], Awaitable[None]]

_FEED_CONTENT_TYPES = {
    "application/atom+xml",
    "application/rss+xml",
    "application/xml",
    "text/xml",
}
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}


class RssFetchError(Exception):
    """Base error for a bounded RSS fetch."""


class ResponseLimitError(RssFetchError):
    """Raised when declared or streamed response size crosses the limit."""


class UnsupportedContentTypeError(RssFetchError):
    """Raised when the endpoint did not return a feed-like media type."""


class RedirectLimitError(RssFetchError):
    """Raised when a feed crosses the configured redirect limit."""


class FetchHttpStatusError(RssFetchError):
    def __init__(self, status_code: int, headers: httpx.Headers) -> None:
        super().__init__(f"RSS endpoint returned HTTP {status_code}")
        self.status_code = status_code
        self.headers = headers


@dataclass(frozen=True, slots=True)
class FetchedRss:
    final_url: str
    status_code: int
    content: bytes
    content_type: str


def create_rss_http_client(
    *,
    max_connections: int = 20,
    max_keepalive_connections: int = 10,
) -> httpx.AsyncClient:
    """Create the production client; its owner must close it during shutdown."""
    return httpx.AsyncClient(
        timeout=httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0),
        limits=httpx.Limits(
            max_connections=max_connections,
            max_keepalive_connections=max_keepalive_connections,
        ),
        follow_redirects=False,
        trust_env=False,
        headers={"User-Agent": "FootballPulse/0.1 RSS discovery"},
    )


class RssFetcher:
    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        safety_policy: UrlSafetyPolicy,
        retry_policy: RetryPolicy | None = None,
        max_response_bytes: int = 2 * 1024 * 1024,
        max_redirects: int = 3,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        if max_response_bytes < 1 or max_redirects < 0:
            raise ValueError("response and redirect limits must not be negative")
        self._client = client
        self._safety = safety_policy
        self._retry = retry_policy or RetryPolicy()
        self._max_response_bytes = max_response_bytes
        self._max_redirects = max_redirects
        self._sleep = sleep

    async def fetch(self, url: str, *, allowed_domains: tuple[str, ...]) -> FetchedRss:
        for attempt in range(1, self._retry.max_attempts + 1):
            try:
                return await self._fetch_once(url, allowed_domains=allowed_domains)
            except FetchHttpStatusError as exc:
                delay = self._retry.delay_for_status(
                    exc.status_code,
                    attempt=attempt,
                    headers=exc.headers,
                )
                if delay is None:
                    raise
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                delay = self._retry.delay_for_exception(exc, attempt=attempt)
                if delay is None:
                    raise
            await self._sleep(delay)
        raise AssertionError("retry loop ended without a result")

    async def _fetch_once(
        self,
        url: str,
        *,
        allowed_domains: tuple[str, ...],
    ) -> FetchedRss:
        validated = await self._safety.validate(url, allowed_domains=allowed_domains)
        redirects = 0
        while True:
            async with self._client.stream("GET", validated.url) as response:
                if response.status_code in _REDIRECT_STATUSES:
                    location = response.headers.get("Location")
                    if location is None:
                        raise RssFetchError("redirect response omitted Location")
                    if redirects >= self._max_redirects:
                        raise RedirectLimitError("RSS redirect limit exceeded")
                    validated = await self._safety.validate_redirect(
                        current_url=validated.url,
                        location=location,
                        allowed_domains=allowed_domains,
                    )
                    redirects += 1
                    continue
                if response.status_code < 200 or response.status_code >= 300:
                    raise FetchHttpStatusError(response.status_code, response.headers)

                content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
                if content_type not in _FEED_CONTENT_TYPES:
                    raise UnsupportedContentTypeError(
                        f"unsupported RSS content type: {content_type or 'missing'}"
                    )
                declared_length = response.headers.get("Content-Length")
                if declared_length is not None:
                    try:
                        parsed_length = int(declared_length)
                        if parsed_length < 0:
                            raise ValueError
                        if parsed_length > self._max_response_bytes:
                            raise ResponseLimitError("RSS response exceeds declared size limit")
                    except ValueError as exc:
                        raise RssFetchError("invalid Content-Length header") from exc

                chunks: list[bytes] = []
                received = 0
                async for chunk in response.aiter_bytes():
                    received += len(chunk)
                    if received > self._max_response_bytes:
                        raise ResponseLimitError("RSS response exceeds streamed size limit")
                    chunks.append(chunk)
                return FetchedRss(
                    final_url=validated.url,
                    status_code=response.status_code,
                    content=b"".join(chunks),
                    content_type=content_type,
                )
