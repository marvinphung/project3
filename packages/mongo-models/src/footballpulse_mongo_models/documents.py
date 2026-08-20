from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar
from uuid import UUID

from beanie import Document, Indexed
from pydantic import BaseModel, ConfigDict, Field


class EntityAlias(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str
    normalized_value: str
    case_sensitive: bool = False


class CanonicalEntity(Document):
    id: UUID
    entity_type: str
    canonical_key: Indexed(str, unique=True)
    canonical_name: str
    canonical_name_normalized: str
    leagues: list[str] = Field(default_factory=list)
    seasons: list[str] = Field(default_factory=list)
    aliases: list[EntityAlias] = Field(default_factory=list)
    alias_values_normalized: list[str] = Field(default_factory=list)
    status: str = "ACTIVE"
    source: str
    created_at: datetime
    updated_at: datetime

    class Settings:
        name = "canonical_entities"
        indexes: ClassVar = [
            [("entity_type", 1), ("canonical_name_normalized", 1)],
            [("alias_values_normalized", 1)],
            [("status", 1), ("updated_at", -1)],
        ]


class EntityMention(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    text: str
    score: float = Field(ge=0, le=1)
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    canonical_entity_id: UUID | None = None
    canonical_name: str | None = None


class EnrichmentClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str
    subject_entity_id: UUID | None = None
    predicate: str
    object: str
    object_entity_id: UUID | None = None
    object_value: dict[str, Any] | None = None
    certainty: str
    evidence_quote: str
    evidence_start: int = Field(ge=0)
    evidence_end: int = Field(ge=0)


class NewsMetadata(Document):
    id: UUID
    url: str
    canonical_url: Indexed(str, unique=True)
    domain_name: Indexed(str)
    source_name: str
    title: str
    description: str | None = None
    published_time: Indexed(datetime) | None = None
    crawl_date: datetime
    image_url: str | None = None
    tags: list[str] = Field(default_factory=list)
    article_keywords: list[str] = Field(default_factory=list)
    content_hash: str
    language: str = "en"

    class Settings:
        name = "news_metadata"
        indexes: ClassVar = [
            [("published_time", -1)],
            [("domain_name", 1), ("published_time", -1)],
            [("title", "text"), ("description", "text")],
        ]


class NewsContent(Document):
    id: UUID
    content: str
    filtered_content: str | None = None
    cleaned_at: datetime
    filtered_at: datetime | None = None
    extractor: str
    extraction_status: str

    class Settings:
        name = "news_content"
        indexes: ClassVar = [[("cleaned_at", -1)], [("filtered_at", -1)]]


class NewsEntity(Document):
    id: UUID
    entities: list[EntityMention] = Field(default_factory=list)
    model_name: str
    model_version: str
    processed_at: datetime

    class Settings:
        name = "news_entities"
        indexes: ClassVar = [
            [("entities.label", 1)],
            [("entities.canonical_entity_id", 1)],
            [("entities.canonical_name", 1)],
            [("processed_at", -1)],
        ]


class EntityTimelineSummary(Document):
    id: UUID
    entity_id: UUID
    canonical_name: str
    entity_type: str
    window_start: datetime
    window_end: datetime
    article_ids: list[UUID] = Field(default_factory=list)
    article_count: int = Field(ge=0)
    entities_50: list[str] = Field(default_factory=list)
    entities_80: list[str] = Field(default_factory=list)
    aggregated_news: str = ""
    short_description: str = ""
    status: str = "COMPLETED"
    error_message: str | None = None
    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    class Settings:
        name = "entity_timeline_summaries"
        indexes: ClassVar = [
            [("entity_id", 1), ("window_start", -1), ("window_end", -1)],
            [("status", 1), ("window_start", -1)],
            [("canonical_name", 1), ("window_start", -1)],
            [("window_start", -1), ("window_end", -1)],
        ]


class NewsEnrichment(Document):
    id: UUID
    event_type: str
    summary_en: str
    summary_vi: str
    claims: list[EnrichmentClaim] = Field(default_factory=list)
    validation_status: str
    model_name: str
    model_version: str
    prompt_version: str
    processed_at: datetime

    class Settings:
        name = "news_enrichments"
        indexes: ClassVar = [
            [("validation_status", 1), ("processed_at", -1)],
            [("event_type", 1), ("processed_at", -1)],
            [("claims.subject_entity_id", 1)],
            [("claims.object_entity_id", 1)],
        ]


class NewsEmbedding(Document):
    id: UUID
    embedding: list[float]
    model_name: str
    dimensions: int = Field(gt=0)
    created_at: datetime

    class Settings:
        name = "news_embeddings"
        indexes: ClassVar = [[("model_name", 1), ("created_at", -1)]]
