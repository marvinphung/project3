from __future__ import annotations

from datetime import date as Date
from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

CONTRACT_VERSION = "article-enrichment.v1"


class EntityType(StrEnum):
    PLAYER = "PLAYER"
    CLUB = "CLUB"
    COACH = "COACH"
    COMPETITION = "COMPETITION"


class EventType(StrEnum):
    TRANSFER = "TRANSFER"
    CONTRACT = "CONTRACT"
    INJURY = "INJURY"
    MATCH = "MATCH"
    MANAGERIAL = "MANAGERIAL"
    DISCIPLINARY = "DISCIPLINARY"
    OTHER = "OTHER"


class Predicate(StrEnum):
    EXPRESSED_INTEREST = "EXPRESSED_INTEREST"
    CONTACTED = "CONTACTED"
    SUBMITTED_BID = "SUBMITTED_BID"
    ACCEPTED_BID = "ACCEPTED_BID"
    REJECTED_BID = "REJECTED_BID"
    COMPLETED_TRANSFER = "COMPLETED_TRANSFER"
    NEGOTIATING_CONTRACT = "NEGOTIATING_CONTRACT"
    SIGNED_CONTRACT = "SIGNED_CONTRACT"
    SUFFERED_INJURY = "SUFFERED_INJURY"
    EXPECTED_RETURN = "EXPECTED_RETURN"
    MATCH_SCHEDULED = "MATCH_SCHEDULED"
    MATCH_RESULT = "MATCH_RESULT"
    APPOINTED_COACH = "APPOINTED_COACH"
    DISMISSED_COACH = "DISMISSED_COACH"
    DENIED_REPORT = "DENIED_REPORT"


class ClaimCertainty(StrEnum):
    RUMOR = "RUMOR"
    REPORTED = "REPORTED"
    CONFIRMED = "CONFIRMED"
    DENIED = "DENIED"


class CanonicalEntityInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    entity_id: UUID
    entity_type: EntityType
    canonical_name: str = Field(min_length=1, max_length=200)


class UnresolvedMentionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    text: str = Field(min_length=1, max_length=200)
    predicted_type: EntityType
    start: Annotated[int, Field(strict=True, ge=0)]
    end: Annotated[int, Field(strict=True, gt=0)]
    score: Annotated[float, Field(strict=True, ge=0, le=1)]

    @model_validator(mode="after")
    def validate_offsets(self) -> Self:
        if self.end <= self.start:
            raise ValueError("unresolved mention end must be after start")
        return self


class ArticleEnrichmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    contract_version: Literal["article-enrichment.v1"]
    article_version_id: UUID
    input_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    title: str = Field(min_length=1, max_length=1_000)
    cleaned_content: str = Field(min_length=1, max_length=500_000)
    published_at: AwareDatetime | None
    source_id: UUID
    source_reliability_tier: Annotated[int, Field(strict=True, ge=1, le=5)]
    canonical_entities: tuple[CanonicalEntityInput, ...] = Field(max_length=200)
    unresolved_mentions: tuple[UnresolvedMentionInput, ...] = Field(max_length=500)

    @model_validator(mode="after")
    def validate_unique_entity_ids_and_mention_offsets(self) -> Self:
        entity_ids = [entity.entity_id for entity in self.canonical_entities]
        if len(entity_ids) != len(set(entity_ids)):
            raise ValueError("canonical entity IDs must be unique")
        for mention in self.unresolved_mentions:
            if mention.end > len(self.cleaned_content):
                raise ValueError("unresolved mention offset is outside cleaned content")
            if self.cleaned_content[mention.start : mention.end] != mention.text:
                raise ValueError("unresolved mention text must match cleaned content offsets")
        return self


class ClaimQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    amount: Annotated[int, Field(strict=True, ge=0)] | None = None
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    injury: str | None = Field(default=None, min_length=1, max_length=200)
    score: str | None = Field(default=None, pattern=r"^\d{1,3}-\d{1,3}$")

    @model_validator(mode="after")
    def validate_amount_currency_pair(self) -> Self:
        if (self.amount is None) is not (self.currency is None):
            raise ValueError("amount and currency must be supplied together")
        if self.date is not None:
            try:
                Date.fromisoformat(self.date)
            except ValueError as error:
                raise ValueError("claim date must be a real ISO calendar date") from error
        return self


class ClaimOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    subject_entity_id: UUID
    predicate: Predicate
    object_entity_id: UUID | None
    object_text: str | None = Field(default=None, min_length=1, max_length=500)
    qualifiers: ClaimQualifiers
    certainty: ClaimCertainty
    evidence_quote: str = Field(min_length=1, max_length=4_000)
    evidence_start: Annotated[int, Field(strict=True, ge=0)]
    evidence_end: Annotated[int, Field(strict=True, gt=0)]

    @model_validator(mode="after")
    def validate_object_and_offsets(self) -> Self:
        if (self.object_entity_id is None) == (self.object_text is None):
            raise ValueError("claim requires exactly one object representation")
        if self.evidence_end <= self.evidence_start:
            raise ValueError("claim evidence end must be after start")
        return self


class ArticleEnrichmentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    contract_version: Literal["article-enrichment.v1"]
    article_version_id: UUID
    input_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    event_type: EventType
    summary_en: str = Field(min_length=1, max_length=4_000)
    claims: tuple[ClaimOutput, ...] = Field(max_length=500)
    model_version: str = Field(min_length=1, max_length=200)
    prompt_version: str = Field(min_length=1, max_length=200)
