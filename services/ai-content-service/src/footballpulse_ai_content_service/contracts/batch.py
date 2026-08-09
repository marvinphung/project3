from __future__ import annotations

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from footballpulse_ai_content_service.contracts.enrichment import ArticleEnrichmentOutput


class SuccessfulBatchRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    article_version_id: UUID
    status: Literal["SUCCESS"]
    result: ArticleEnrichmentOutput

    @model_validator(mode="after")
    def validate_article_identity(self) -> Self:
        if self.article_version_id != self.result.article_version_id:
            raise ValueError("batch record article must match enrichment result")
        return self


class FailedBatchRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    article_version_id: UUID
    status: Literal["ERROR"]
    error_code: str = Field(min_length=1, max_length=80, pattern=r"^[A-Z][A-Z0-9_]*$")
    error: str = Field(min_length=1, max_length=500)


BatchRecord = Annotated[
    SuccessfulBatchRecord | FailedBatchRecord,
    Field(discriminator="status"),
]
BATCH_RECORD_ADAPTER: TypeAdapter[BatchRecord] = TypeAdapter(BatchRecord)
