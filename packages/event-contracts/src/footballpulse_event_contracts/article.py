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


