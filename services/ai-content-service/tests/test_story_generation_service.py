from __future__ import annotations

from uuid import UUID

import pytest
from footballpulse_ai_content_service.contracts.generation import (
    GeneratedStoryArticle,
    GroundedStoryClaim,
    StoryArticleGenerationInput,
)
from footballpulse_ai_content_service.providers.base import FallbackReason, ProviderFailure
from footballpulse_ai_content_service.services.generation import GroundedArticleGenerationService

STORY_ID = UUID(int=1)
CLAIM_ID = UUID(int=2)
SOURCE_ID = UUID(int=3)


def request() -> StoryArticleGenerationInput:
    return StoryArticleGenerationInput(
        story_id=STORY_ID,
        story_version=2,
        title_context_en="Arsenal bid for Vinicius",
        claims=(
            GroundedStoryClaim(
                claim_id=CLAIM_ID,
                statement_en="Arsenal submitted a bid.",
                source_article_ids=(SOURCE_ID,),
            ),
        ),
        source_article_ids=(SOURCE_ID,),
        prompt_version="story-article-v1",
    )


class FakeProvider:
    def __init__(self, output: GeneratedStoryArticle) -> None:
        self.output = output

    def generate(self, source: StoryArticleGenerationInput) -> GeneratedStoryArticle:
        return self.output


def output(**overrides: object) -> GeneratedStoryArticle:
    values: dict[str, object] = {
        "story_id": STORY_ID,
        "story_version": 2,
        "title_en": "Arsenal bid for Vinicius",
        "body_en": "Arsenal submitted a bid.",
        "title_vi": "Arsenal hỏi mua Vinicius",
        "body_vi": "Arsenal đã gửi đề nghị.",
        "used_claim_ids": (CLAIM_ID,),
        "used_source_article_ids": (SOURCE_ID,),
        "model_version": "mock-v1",
        "prompt_version": "story-article-v1",
    }
    values.update(overrides)
    return GeneratedStoryArticle(**values)


def test_service_returns_provider_output_when_grounded() -> None:
    service = GroundedArticleGenerationService(FakeProvider(output()))

    result = service.generate(request())

    assert result == output()


def test_service_rejects_output_from_wrong_story_version() -> None:
    service = GroundedArticleGenerationService(FakeProvider(output(story_version=3)))

    with pytest.raises(ProviderFailure) as error:
        service.generate(request())

    assert error.value.reason is FallbackReason.OUTPUT_GROUNDING


def test_service_rejects_output_claim_not_in_input() -> None:
    service = GroundedArticleGenerationService(FakeProvider(output(used_claim_ids=(UUID(int=99),))))

    with pytest.raises(ProviderFailure, match="claim"):
        service.generate(request())
