from __future__ import annotations

import pytest
from footballpulse_crawler_service.discovery.security import (
    UnsafeUrlError,
    UrlSafetyPolicy,
)


async def _public_resolver(host: str, port: int) -> tuple[str, ...]:
    del host, port
    return ("93.184.216.34",)


@pytest.mark.anyio
async def test_accepts_public_http_url_on_allowed_host() -> None:
    policy = UrlSafetyPolicy(resolver=_public_resolver)

    validated = await policy.validate(
        "https://news.example.com/rss.xml",
        allowed_domains=("example.com",),
    )

    assert validated.host == "news.example.com"
    assert validated.port == 443
    assert validated.addresses == ("93.184.216.34",)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("url", "addresses"),
    [
        ("file:///etc/passwd", ("93.184.216.34",)),
        ("https://user:secret@example.com/feed", ("93.184.216.34",)),
        ("https://evil.test/feed", ("93.184.216.34",)),
        ("https://news.example.com/feed", ("127.0.0.1",)),
        ("https://news.example.com/feed", ("10.0.0.1",)),
        ("https://news.example.com/feed", ("169.254.169.254",)),
        ("https://news.example.com/feed", ("::1",)),
        ("https://news.example.com/feed", ("93.184.216.34", "10.0.0.1")),
    ],
)
async def test_rejects_unsafe_url_or_any_unsafe_resolved_address(
    url: str,
    addresses: tuple[str, ...],
) -> None:
    async def resolver(host: str, port: int) -> tuple[str, ...]:
        del host, port
        return addresses

    policy = UrlSafetyPolicy(resolver=resolver)

    with pytest.raises(UnsafeUrlError):
        await policy.validate(url, allowed_domains=("example.com",))


@pytest.mark.anyio
async def test_rejects_host_that_does_not_resolve() -> None:
    async def resolver(host: str, port: int) -> tuple[str, ...]:
        del host, port
        return ()

    policy = UrlSafetyPolicy(resolver=resolver)

    with pytest.raises(UnsafeUrlError, match="resolve"):
        await policy.validate(
            "https://news.example.com/feed",
            allowed_domains=("example.com",),
        )


@pytest.mark.anyio
async def test_redirect_is_resolved_then_revalidated() -> None:
    policy = UrlSafetyPolicy(resolver=_public_resolver)

    redirected = await policy.validate_redirect(
        current_url="https://news.example.com/rss/feed.xml",
        location="../latest.xml",
        allowed_domains=("example.com",),
    )

    assert redirected.url == "https://news.example.com/latest.xml"


@pytest.mark.anyio
async def test_redirect_cannot_escape_allowlist() -> None:
    policy = UrlSafetyPolicy(resolver=_public_resolver)

    with pytest.raises(UnsafeUrlError, match="allowlist"):
        await policy.validate_redirect(
            current_url="https://news.example.com/feed",
            location="https://attacker.test/feed",
            allowed_domains=("example.com",),
        )
