from __future__ import annotations

import asyncio

import httpx

from footballpulse_crawler_service.discovery.fetcher import (
    BoundedHttpFetcher,
    FetchedHttpResponse,
    Sleep,
)
from footballpulse_crawler_service.discovery.retry import RetryPolicy
from footballpulse_crawler_service.discovery.security import UrlSafetyPolicy

FetchedHtml = FetchedHttpResponse


class HtmlFetcher(BoundedHttpFetcher):
    """Bounded HTML transport sharing the RSS network security boundary."""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        safety_policy: UrlSafetyPolicy,
        retry_policy: RetryPolicy | None = None,
        max_response_bytes: int = 5 * 1024 * 1024,
        max_redirects: int = 3,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        super().__init__(
            client=client,
            safety_policy=safety_policy,
            retry_policy=retry_policy,
            max_response_bytes=max_response_bytes,
            max_redirects=max_redirects,
            sleep=sleep,
            accepted_content_types=frozenset({"text/html", "application/xhtml+xml"}),
            resource_name="HTML",
        )
