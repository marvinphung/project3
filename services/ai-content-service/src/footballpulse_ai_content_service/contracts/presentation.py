from __future__ import annotations

from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class VietnameseProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    summary_vi: str = Field(min_length=1, max_length=10_000)
    used_claim_ids: tuple[UUID, ...] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_unique_claim_ids(self) -> Self:
        if len(self.used_claim_ids) != len(set(self.used_claim_ids)):
            raise ValueError("Vietnamese projection claim IDs must be unique")
        return self
