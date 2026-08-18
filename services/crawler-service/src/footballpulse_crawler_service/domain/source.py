from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum
from urllib.parse import urlsplit
from uuid import UUID

from footballpulse_crawler_service.domain.errors import DomainValidationError


class SourceType(StrEnum):
    RSS = "RSS"
    SITEMAP = "SITEMAP"
    HTML = "HTML"


def normalize_domain(value: str) -> str:
    candidate = value.strip().lower().rstrip(".")
    if not candidate or "://" in candidate or "/" in candidate or ":" in candidate:
        raise DomainValidationError("allowed domain must be a hostname without scheme or port")
    try:
        return candidate.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise DomainValidationError("allowed domain is not a valid hostname") from exc


def feed_host(rss_url: str) -> str:
    parsed = urlsplit(rss_url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
        raise DomainValidationError("RSS URL must use http or https and include a host")
    if parsed.username is not None or parsed.password is not None:
        raise DomainValidationError("RSS URL must not contain credentials")
    return normalize_domain(parsed.hostname)


def host_is_allowed(host: str, domains: tuple[str, ...]) -> bool:
    return any(host == domain or host.endswith(f".{domain}") for domain in domains)


@dataclass(frozen=True, slots=True)
class NewSource:
    name: str
    rss_url: str
    allowed_domains: tuple[str, ...]
    source_type: SourceType
    reliability_tier: int
    crawl_interval_minutes: int
    max_concurrency: int

    @classmethod
    def create(
        cls,
        *,
        name: str,
        rss_url: str,
        allowed_domains: list[str],
        source_type: SourceType,
        reliability_tier: int,
        crawl_interval_minutes: int,
        max_concurrency: int,
    ) -> NewSource:
        normalized_name = name.strip()
        if not normalized_name or len(normalized_name) > 200:
            raise DomainValidationError("source name must contain 1 to 200 characters")
        normalized_domains = tuple(sorted({normalize_domain(item) for item in allowed_domains}))
        if not normalized_domains:
            raise DomainValidationError("at least one allowed domain is required")
        if not host_is_allowed(feed_host(rss_url), normalized_domains):
            raise DomainValidationError("RSS host must be allowed by allowed domains")
        if not 1 <= reliability_tier <= 5:
            raise DomainValidationError("reliability tier must be between 1 and 5")
        if crawl_interval_minutes <= 0:
            raise DomainValidationError("crawl interval must be positive")
        if max_concurrency <= 0:
            raise DomainValidationError("max concurrency must be positive")
        return cls(
            name=normalized_name,
            rss_url=rss_url,
            allowed_domains=normalized_domains,
            source_type=source_type,
            reliability_tier=reliability_tier,
            crawl_interval_minutes=crawl_interval_minutes,
            max_concurrency=max_concurrency,
        )


@dataclass(frozen=True, slots=True)
class Source:
    id: UUID
    name: str
    rss_url: str
    allowed_domains: tuple[str, ...]
    source_type: SourceType
    reliability_tier: int
    enabled: bool
    crawl_interval_minutes: int
    max_concurrency: int
    last_discovered_at: datetime | None
    created_at: datetime
    updated_at: datetime
    version: int

    def is_due(self, at: datetime) -> bool:
        if not self.enabled:
            return False
        if self.last_discovered_at is None:
            return True
        return self.last_discovered_at + timedelta(minutes=self.crawl_interval_minutes) <= at

    def with_enabled(self, enabled: bool, *, now: datetime) -> Source:
        if enabled == self.enabled:
            return self
        return replace(self, enabled=enabled, updated_at=now, version=self.version + 1)

    def with_configuration(self, configuration: NewSource, *, now: datetime) -> Source:
        return replace(
            self,
            name=configuration.name,
            rss_url=configuration.rss_url,
            allowed_domains=configuration.allowed_domains,
            source_type=configuration.source_type,
            reliability_tier=configuration.reliability_tier,
            crawl_interval_minutes=configuration.crawl_interval_minutes,
            max_concurrency=configuration.max_concurrency,
            updated_at=now,
            version=self.version + 1,
        )
