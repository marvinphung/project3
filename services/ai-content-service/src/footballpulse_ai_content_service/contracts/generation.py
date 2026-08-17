from __future__ import annotations

from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GroundedStoryClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    claim_id: UUID
    statement_en: str = Field(min_length=1, max_length=4_000)
    source_article_ids: tuple[UUID, ...] = Field(min_length=1, max_length=500)


class StoryArticleGenerationInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    story_id: UUID
    story_version: int = Field(strict=True, ge=1)
    title_context_en: str = Field(min_length=1, max_length=1_000)
    claims: tuple[GroundedStoryClaim, ...] = Field(min_length=1, max_length=500)
    source_article_ids: tuple[UUID, ...] = Field(min_length=1, max_length=500)
    prompt_version: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_claim_sources(self) -> Self:
        allowed_sources = set(self.source_article_ids)
        if any(not set(claim.source_article_ids) <= allowed_sources for claim in self.claims):
            raise ValueError("claim evidence source is outside generation input")
        return self


class GeneratedStoryArticle(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    story_id: UUID
    story_version: int = Field(strict=True, ge=1)
    title_en: str = Field(min_length=1, max_length=1_000)
    body_en: str = Field(min_length=1, max_length=100_000)
    title_vi: str = Field(min_length=1, max_length=1_000)
    body_vi: str = Field(min_length=1, max_length=100_000)
    used_claim_ids: tuple[UUID, ...] = Field(min_length=1, max_length=500)
    used_source_article_ids: tuple[UUID, ...] = Field(min_length=1, max_length=500)
    model_version: str = Field(min_length=1, max_length=200)
    prompt_version: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_unique_grounding_ids(self) -> Self:
        if len(self.used_claim_ids) != len(set(self.used_claim_ids)):
            raise ValueError("generated article claim IDs must be unique")
        if len(self.used_source_article_ids) != len(set(self.used_source_article_ids)):
            raise ValueError("generated article source IDs must be unique")
        return self
