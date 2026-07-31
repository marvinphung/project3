from datetime import timedelta
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    model_validator,
)

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ResponseHeaders(BaseModel):
    """Allowlisted response headers safe to carry in an event."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    etag: str | None = None
    last_modified: str | None = Field(default=None, alias="last-modified")
    content_language: str | None = Field(default=None, alias="content-language")


class ArticleDiscoveredPayloadV1(BaseModel):
    """Bounded parsed source snapshot produced by the Crawler Service."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    discovery_id: UUID
    source_id: UUID
    crawl_batch_id: UUID
    source_name: Annotated[NonEmptyText, StringConstraints(max_length=200)]
    source_domain: Annotated[NonEmptyText, StringConstraints(max_length=253)]
    original_url: HttpUrl
    canonical_url_hint: HttpUrl | None = None
    original_title: Annotated[NonEmptyText, StringConstraints(max_length=500)]
    parsed_content: Annotated[NonEmptyText, StringConstraints(max_length=200_000)]
    author: Annotated[str, StringConstraints(max_length=200)] | None = None
    published_at: AwareDatetime | None = None
    collected_at: AwareDatetime
    language: Annotated[str, StringConstraints(pattern=r"^[a-z]{2,3}(-[A-Z]{2})?$")]
    http_status: int = Field(ge=200, le=299)
    content_type: Annotated[NonEmptyText, StringConstraints(max_length=200)]
    response_headers: ResponseHeaders

    @model_validator(mode="after")
    def timestamps_must_be_utc(self) -> Self:
        timestamps = (self.published_at, self.collected_at)
        if any(
            timestamp is not None and timestamp.utcoffset() != timedelta(0)
            for timestamp in timestamps
        ):
            raise ValueError("article timestamps must use UTC")
        return self


class ArticleDiscoveredV1(BaseModel):
    """Kafka contract for one bounded Crawler discovery."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: UUID
    event_type: Literal["article.discovered"]
    schema_version: Literal[1]
    occurred_at: AwareDatetime
    producer: Literal["crawler-service"]
    correlation_id: UUID
    causation_id: UUID | None
    aggregate_id: UUID
    traceparent: (
        Annotated[
            str,
            StringConstraints(
                pattern=r"^[0-9a-f]{2}-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$"
            ),
        ]
        | None
    ) = None
    payload: ArticleDiscoveredPayloadV1

    @model_validator(mode="after")
    def validate_envelope_invariants(self) -> Self:
        if self.occurred_at.utcoffset() != timedelta(0):
            raise ValueError("occurred_at must use UTC")
        if self.aggregate_id != self.payload.discovery_id:
            raise ValueError("aggregate_id must equal payload.discovery_id")
        return self
