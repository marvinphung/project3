from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from footballpulse_shared import article_id_from_url, canonicalize_news_url

V2_CANDIDATE_LIMIT = 500
V2_SCHEDULED_FETCH_LIMIT = 100
V2_BOOTSTRAP_FETCH_LIMIT = 500
DEFAULT_MAX_AGE_DAYS = 30


def is_within_age_limit(
    published_at: datetime | None,
    *,
    max_days: int = DEFAULT_MAX_AGE_DAYS,
    reference_time: datetime | None = None,
) -> bool:
    """Return True if published_at is within the last max_days (or if published_at is None)."""
    if published_at is None:
        return True
    now = reference_time or datetime.now(UTC)
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=UTC)
    age = now - published_at
    # Allow up to max_days in the past, and allow up to 1 day clock skew into the future
    return age <= timedelta(days=max_days) and age >= timedelta(days=-1)


@dataclass(frozen=True, slots=True)
class CrawlCandidate:
    article_id: UUID
    url: str


def select_new_candidates(
    urls: Iterable[str],
    *,
    exists: Callable[[UUID], bool],
    candidate_limit: int = V2_CANDIDATE_LIMIT,
    fetch_limit: int = V2_SCHEDULED_FETCH_LIMIT,
) -> list[CrawlCandidate]:
    """Canonicalize and deduplicate before any article HTML fetch."""
    if candidate_limit < 1 or fetch_limit < 1:
        raise ValueError("crawl limits must be positive")

    selected: list[CrawlCandidate] = []
    seen: set[UUID] = set()
    for raw_url in urls:
        if len(seen) >= candidate_limit:
            break
        canonical_url = canonicalize_news_url(raw_url)
        article_id = article_id_from_url(canonical_url)
        if article_id in seen:
            continue
        seen.add(article_id)
        if exists(article_id):
            continue
        selected.append(CrawlCandidate(article_id=article_id, url=canonical_url))
        if len(selected) >= fetch_limit:
            break
    return selected
