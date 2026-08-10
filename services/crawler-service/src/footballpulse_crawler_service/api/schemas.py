from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl

from footballpulse_crawler_service.domain.crawl_batch import CrawlBatch, CrawlBatchStatus
from footballpulse_crawler_service.domain.source import NewSource, Source, SourceType


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[dict[str, object]] = Field(default_factory=list)


class ErrorEnvelope(BaseModel):
    error: ErrorBody


class SourceConfigurationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    rss_url: HttpUrl
    allowed_domains: list[str]
    source_type: SourceType
    reliability_tier: int
    crawl_interval_minutes: int
    max_concurrency: int

    def to_domain(self) -> NewSource:
        return NewSource.create(
            name=self.name,
            rss_url=str(self.rss_url),
            allowed_domains=self.allowed_domains,
            source_type=self.source_type,
            reliability_tier=self.reliability_tier,
            crawl_interval_minutes=self.crawl_interval_minutes,
            max_concurrency=self.max_concurrency,
        )


class SourceUpdateRequest(SourceConfigurationRequest):
    expected_version: int = Field(ge=1)


class SourceToggleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    expected_version: int = Field(ge=1)


class CrawlTriggerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=1, max_length=256)


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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

    @classmethod
    def from_domain(cls, source: Source) -> SourceResponse:
        return cls.model_validate(source)


class SourceListResponse(BaseModel):
    items: list[SourceResponse]


class CrawlBatchOpenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: UUID
    idempotency_key: str = Field(min_length=1, max_length=256)
    window_started_at: AwareDatetime


class CrawlBatchCompleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal[
        CrawlBatchStatus.COMPLETED,
        CrawlBatchStatus.PARTIAL,
        CrawlBatchStatus.FAILED,
    ]
    discovered_count: int = Field(ge=0)
    fetched_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)


class CrawlBatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_id: UUID
    idempotency_key: str
    window_started_at: datetime
    status: CrawlBatchStatus
    discovered_count: int
    fetched_count: int
    failed_count: int
    started_at: datetime
    completed_at: datetime | None

    @classmethod
    def from_domain(cls, batch: CrawlBatch) -> CrawlBatchResponse:
        return cls.model_validate(batch)
