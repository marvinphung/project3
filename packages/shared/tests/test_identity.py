from uuid import UUID

import pytest
from footballpulse_shared.identity import article_id_from_url, canonicalize_news_url


def test_canonicalizes_url_for_deduplication() -> None:
    first = canonicalize_news_url(
        "HTTPS://Example.COM:443/news?id=2&utm_source=rss&id=1#comments"
    )
    second = canonicalize_news_url("https://example.com/news?id=1&id=2")

    assert first == second == "https://example.com/news?id=1&id=2"
    assert article_id_from_url(first) == article_id_from_url(second)


def test_article_id_is_uuid() -> None:
    assert isinstance(article_id_from_url("https://example.com/news"), UUID)


@pytest.mark.parametrize(
    "value",
    ["", "example.com/news", "ftp://example.com/news", "https://user:pass@example.com/news"],
)
def test_rejects_invalid_news_url(value: str) -> None:
    with pytest.raises(ValueError):
        canonicalize_news_url(value)
