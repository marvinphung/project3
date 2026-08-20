from __future__ import annotations

from typing import Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl, model_validator

from footballpulse_event_contracts.envelope import EventEnvelope


class NewsCrawledPayload(BaseModel):
    """Mongo pointer published after the v2 crawler write succeeds."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    article_id: UUID
    canonical_url: HttpUrl
    source_name: str = Field(min_length=1, max_length=200)
    published_time: AwareDatetime | None


class NewsCrawledEvent(EventEnvelope):
    event_type: Literal["news.crawled"]
    event_version: Literal[1]
    producer: Literal["crawler-service"]
    aggregate_type: Literal["news_article"]
    payload: NewsCrawledPayload

    @model_validator(mode="after")
    def validate_aggregate_identity(self) -> Self:
        if self.aggregate_id != self.payload.article_id:
            raise ValueError("crawled aggregate must match article identity")
        return self


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

