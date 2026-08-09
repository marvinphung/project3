from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class EventEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: UUID
    event_type: str = Field(min_length=1, max_length=120, pattern=r"^[a-z][a-z0-9.]*$")
    event_version: int = Field(ge=1)
    occurred_at: AwareDatetime
    producer: str = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9-]*$")
    correlation_id: UUID
    causation_id: UUID | None
    aggregate_type: str = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    aggregate_id: UUID
    idempotency_key: str = Field(min_length=1, max_length=256)


def event_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **model.model_json_schema(mode="validation"),
    }
