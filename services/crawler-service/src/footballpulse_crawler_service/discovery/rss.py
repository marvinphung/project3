from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit

import feedparser  # type: ignore[import-untyped]

from footballpulse_crawler_service.domain.source import host_is_allowed, normalize_domain


class RssParseError(ValueError):
    """Raised when a response cannot produce any usable RSS entry."""


@dataclass(frozen=True, slots=True)
class RssEntry:
    guid: str
    title: str
    url: str
    published_at: datetime | None


@dataclass(frozen=True, slots=True)
class ParsedRss:
    feed_title: str | None
    entries: tuple[RssEntry, ...]
    skipped_entries: int
    truncated: bool
    parse_warning: str | None


def _entry_url(value: object, allowed_domains: tuple[str, ...]) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
        return None
    if parsed.username is not None or parsed.password is not None:
        return None
    try:
        host = normalize_domain(parsed.hostname)
        port = parsed.port
    except ValueError:
        return None
    if port is not None and port not in {80, 443}:
        return None
    if not host_is_allowed(host, allowed_domains):
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", parsed.query, ""))


def _published_at(entry: object) -> datetime | None:
    value = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if value is None:
        return None
    return datetime.fromtimestamp(calendar.timegm(value), tz=UTC)


def parse_rss(
    payload: bytes,
    *,
    allowed_domains: tuple[str, ...],
    max_entries: int,
) -> ParsedRss:
    if max_entries < 1:
        raise ValueError("max_entries must be positive")
    parsed = feedparser.parse(payload)
    entries: list[RssEntry] = []
    skipped = 0
    truncated = False
    for candidate in parsed.entries:
        url = _entry_url(candidate.get("link"), allowed_domains)
        title = str(candidate.get("title", "")).strip()
        if url is None or not title:
            skipped += 1
            continue
        if len(entries) >= max_entries:
            truncated = True
            continue
        guid = str(candidate.get("id") or url).strip()
        entries.append(
            RssEntry(
                guid=guid[:1000],
                title=title[:500],
                url=url,
                published_at=_published_at(candidate),
            )
        )

    warning = None
    if bool(getattr(parsed, "bozo", False)):
        warning = type(getattr(parsed, "bozo_exception", None)).__name__
    if not entries:
        raise RssParseError(warning or "feed contains no usable entries")
    feed_title = str(parsed.feed.get("title", "")).strip() or None
    return ParsedRss(feed_title, tuple(entries), skipped, truncated, warning)
