from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class AiBatchStatus(StrEnum):
    PREPARING = "PREPARING"
    DATASET_UPLOADED = "DATASET_UPLOADED"
    KERNEL_SUBMITTED = "KERNEL_SUBMITTED"
    RUNNING = "RUNNING"
    DOWNLOADING = "DOWNLOADING"
    IMPORTING = "IMPORTING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_TERMINAL = "FAILED_TERMINAL"


class AiBatchManifestRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    article_version_id: UUID
    input_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class AiBatchManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    contract_version: str = Field(pattern=r"^ai-batch\.v1$")
    batch_id: UUID
    status: AiBatchStatus
    created_at: AwareDatetime
    model_version: str = Field(min_length=1, max_length=200)
    prompt_version: str = Field(min_length=1, max_length=200)
    article_count: int = Field(strict=True, gt=0, le=10_000)
    articles_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    records: tuple[AiBatchManifestRecord, ...] = Field(min_length=1, max_length=10_000)

    @model_validator(mode="after")
    def validate_records(self) -> Self:
        if self.article_count != len(self.records):
            raise ValueError("article_count must match manifest records")
        article_ids = [record.article_version_id for record in self.records]
        if len(article_ids) != len(set(article_ids)):
            raise ValueError("manifest article_version_id values must be unique")
        return self


class AiBatchJob(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    batch_id: UUID
    status: AiBatchStatus
    created_at: AwareDatetime
    updated_at: AwareDatetime
    retry_count: int = Field(default=0, strict=True, ge=0, le=2)
    article_count: int = Field(strict=True, gt=0, le=10_000)
    success_count: int = Field(default=0, strict=True, ge=0)
    error_count: int = Field(default=0, strict=True, ge=0)
    artifact_directory: str = Field(min_length=1, max_length=1_000)
    error_code: str | None = Field(default=None, max_length=80)
    error_detail: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.success_count + self.error_count > self.article_count:
            raise ValueError("job result counts cannot exceed article_count")
        return self


class AiJobReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    contract_version: Literal["ai-job-report.v1"]
    batch_id: UUID
    articles_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    model_version: str = Field(min_length=1, max_length=200)
    prompt_version: str = Field(min_length=1, max_length=200)
    success_count: int = Field(strict=True, ge=0, le=10_000)
    error_count: int = Field(strict=True, ge=0, le=10_000)
    started_at: AwareDatetime
    finished_at: AwareDatetime

    @model_validator(mode="after")
    def validate_timing(self) -> Self:
        if self.finished_at < self.started_at:
            raise ValueError("job report cannot finish before it starts")
        return self
