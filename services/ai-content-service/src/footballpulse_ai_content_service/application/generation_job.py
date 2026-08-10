from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class GenerationTrigger(StrEnum):
    MILESTONE = "MILESTONE"
    MANUAL = "MANUAL"


class GenerationJobState(StrEnum):
    PREPARING = "PREPARING"
    RUNNING = "RUNNING"
    VALIDATING = "VALIDATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class GenerationJob:
    id: UUID
    story_id: UUID
    story_version: int
    prompt_version: str
    trigger: GenerationTrigger
    business_key: str
    state: GenerationJobState

    @classmethod
    def create(
        cls,
        *,
        job_id: UUID,
        story_id: UUID,
        story_version: int,
        prompt_version: str,
        trigger: GenerationTrigger,
    ) -> GenerationJob:
        if story_version < 1:
            raise ValueError("story version must be at least 1")
        normalized_prompt = prompt_version.strip()
        if not normalized_prompt:
            raise ValueError("prompt version must not be empty")
        try:
            generation_trigger = GenerationTrigger(trigger)
        except ValueError as error:
            raise ValueError("unsupported generation trigger") from error
        business_key = f"{story_id}:{story_version}:{normalized_prompt}"
        return cls(
            job_id,
            story_id,
            story_version,
            normalized_prompt,
            generation_trigger,
            business_key,
            GenerationJobState.PREPARING,
        )
