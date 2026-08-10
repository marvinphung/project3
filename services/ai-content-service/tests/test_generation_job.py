from __future__ import annotations

from uuid import UUID

import pytest
from footballpulse_ai_content_service.application.generation_job import (
    GenerationJob,
    GenerationJobState,
    GenerationTrigger,
)

STORY_ID = UUID(int=1)


def test_generation_job_uses_stable_business_key() -> None:
    first = GenerationJob.create(
        job_id=UUID(int=2),
        story_id=STORY_ID,
        story_version=4,
        prompt_version="story-article-v1",
        trigger=GenerationTrigger.MILESTONE,
    )
    second = GenerationJob.create(
        job_id=UUID(int=3),
        story_id=STORY_ID,
        story_version=4,
        prompt_version="story-article-v1",
        trigger=GenerationTrigger.MANUAL,
    )

    assert first.state is GenerationJobState.PREPARING
    assert first.business_key == second.business_key
    assert first.business_key == f"{STORY_ID}:4:story-article-v1"


def test_generation_job_rejects_unsupported_trigger_and_version() -> None:
    with pytest.raises(ValueError, match="trigger"):
        GenerationJob.create(
            job_id=UUID(int=2),
            story_id=STORY_ID,
            story_version=1,
            prompt_version="v1",
            trigger="AUTOMATIC",
        )
    with pytest.raises(ValueError, match="version"):
        GenerationJob.create(
            job_id=UUID(int=2),
            story_id=STORY_ID,
            story_version=0,
            prompt_version="v1",
            trigger=GenerationTrigger.MANUAL,
        )
