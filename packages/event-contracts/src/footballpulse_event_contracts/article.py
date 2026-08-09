from __future__ import annotations

from typing import Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl, model_validator

from footballpulse_event_contracts.envelope import EventEnvelope


class ArticleDiscoveredPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: UUID
    batch_id: UUID
    canonical_url: HttpUrl
    rss_guid: str | None = Field(max_length=512)
    rss_title: str = Field(min_length=1, max_length=512)
    rss_published_at: AwareDatetime | None
    fetched_at: AwareDatetime
    fetch_artifact_id: UUID
    http_status: Literal[200]
    content_type: Literal["text/html", "application/xhtml+xml"]
    content_length: int = Field(ge=1, le=5_000_000)


class ArticleDiscoveredEvent(EventEnvelope):
    event_type: Literal["article.discovered"]
    event_version: Literal[1]
    producer: Literal["crawler-service"]
    aggregate_type: Literal["source_article"]
    payload: ArticleDiscoveredPayload


class ArticleCleanedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: UUID
    article_id: UUID
    article_version_id: UUID
    canonical_url: HttpUrl
    title: str = Field(min_length=1, max_length=512)
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    language: Literal["en"]
    cleaned_at: AwareDatetime
    mongo_collection: Literal["source_articles"]
    mongo_document_id: str = Field(pattern=r"^[a-f0-9]{24}$")
    duplicate_type: Literal["NONE", "URL", "EXACT", "NEAR"]
    duplicate_of_article_version_id: UUID | None

    @model_validator(mode="after")
    def validate_duplicate_reference(self) -> Self:
        has_reference = self.duplicate_of_article_version_id is not None
        if (self.duplicate_type == "NONE") == has_reference:
            raise ValueError("duplicate reference must be absent for NONE and present otherwise")
        return self


class ArticleCleanedEvent(EventEnvelope):
    event_type: Literal["article.cleaned"]
    event_version: Literal[1]
    producer: Literal["article-service"]
    aggregate_type: Literal["article_version"]
    payload: ArticleCleanedPayload


class ArticleEnrichedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    article_version_id: UUID
    input_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    enrichment_id: UUID
    validation_status: Literal["VALIDATED", "PARTIAL"]
    valid_claim_count: int = Field(strict=True, ge=1, le=500)
    rejected_claim_count: int = Field(strict=True, ge=0, le=500)
    model_version: str = Field(min_length=1, max_length=200)
    prompt_version: str = Field(min_length=1, max_length=200)
    validator_version: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_partial_counts(self) -> Self:
        if (self.validation_status == "PARTIAL") is not (self.rejected_claim_count > 0):
            raise ValueError("PARTIAL status must match rejected claim count")
        return self


class ArticleEnrichedEvent(EventEnvelope):
    event_type: Literal["article.enriched"]
    event_version: Literal[1]
    producer: Literal["ai-content-service"]
    aggregate_type: Literal["article_version"]
    payload: ArticleEnrichedPayload

    @model_validator(mode="after")
    def validate_aggregate_identity(self) -> Self:
        if self.aggregate_id != self.payload.article_version_id:
            raise ValueError("enriched aggregate must match article version")
        return self


class ArticleEnrichmentFailedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    article_version_id: UUID
    input_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    error_code: str = Field(min_length=1, max_length=80, pattern=r"^[A-Z][A-Z0-9_]*$")
    retryable: bool = Field(strict=True)
    attempt: int = Field(strict=True, ge=1, le=20)
    model_version: str = Field(min_length=1, max_length=200)
    prompt_version: str = Field(min_length=1, max_length=200)


class ArticleEnrichmentFailedEvent(EventEnvelope):
    event_type: Literal["article.enrichment.failed"]
    event_version: Literal[1]
    producer: Literal["ai-content-service"]
    aggregate_type: Literal["article_version"]
    payload: ArticleEnrichmentFailedPayload

    @model_validator(mode="after")
    def validate_aggregate_identity(self) -> Self:
        if self.aggregate_id != self.payload.article_version_id:
            raise ValueError("failed enrichment aggregate must match article version")
        return self
