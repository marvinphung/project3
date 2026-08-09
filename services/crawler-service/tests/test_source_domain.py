from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from footballpulse_crawler_service.domain.errors import DomainValidationError
from footballpulse_crawler_service.domain.source import NewSource, Source, SourceType


def test_new_source_normalizes_domains_and_requires_the_feed_host_in_allowlist() -> None:
    source = NewSource.create(
        name="  BBC Sport  ",
        rss_url="https://www.bbc.com/sport/football/rss.xml",
        allowed_domains=["BBC.COM.", "www.bbc.com", "bbc.com"],
        source_type=SourceType.RSS,
        reliability_tier=1,
        crawl_interval_minutes=360,
        max_concurrency=2,
    )

    assert source.name == "BBC Sport"
    assert source.allowed_domains == ("bbc.com", "www.bbc.com")

    with pytest.raises(DomainValidationError, match="RSS host must be allowed"):
        NewSource.create(
            name="BBC Sport",
            rss_url="https://www.bbc.com/sport/football/rss.xml",
            allowed_domains=["example.com"],
            source_type=SourceType.RSS,
            reliability_tier=1,
            crawl_interval_minutes=360,
            max_concurrency=2,
        )


@pytest.mark.parametrize("tier", [0, 6])
def test_new_source_rejects_invalid_reliability_tier(tier: int) -> None:
    with pytest.raises(DomainValidationError, match="reliability tier"):
        NewSource.create(
            name="BBC Sport",
            rss_url="https://www.bbc.com/rss.xml",
            allowed_domains=["bbc.com"],
            source_type=SourceType.RSS,
            reliability_tier=tier,
            crawl_interval_minutes=360,
            max_concurrency=2,
        )


def test_source_due_policy_respects_enabled_state_and_interval() -> None:
    now = datetime(2026, 8, 1, 6, tzinfo=UTC)
    source = Source(
        id=uuid4(),
        name="BBC Sport",
        rss_url="https://www.bbc.com/rss.xml",
        allowed_domains=("bbc.com",),
        source_type=SourceType.RSS,
        reliability_tier=1,
        enabled=True,
        crawl_interval_minutes=360,
        max_concurrency=2,
        last_discovered_at=now - timedelta(hours=6),
        created_at=now - timedelta(days=1),
        updated_at=now - timedelta(days=1),
        version=1,
    )

    assert source.is_due(now) is True
    assert source.is_due(now - timedelta(seconds=1)) is False
    assert source.with_enabled(False, now=now).is_due(now + timedelta(days=1)) is False
    assert source.with_enabled(False, now=now).version == 2
