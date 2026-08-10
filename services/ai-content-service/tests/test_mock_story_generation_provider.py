from __future__ import annotations

from uuid import UUID

from footballpulse_ai_content_service.contracts.generation import (
    StoryArticleGenerationInput,
)
from footballpulse_ai_content_service.providers.mock_generation import (
    MockStoryArticleGenerationProvider,
)

STORY_ID = UUID(int=1)
CLAIM_ID = UUID(int=2)
SOURCE_ID = UUID(int=3)


def request() -> StoryArticleGenerationInput:
    return StoryArticleGenerationInput.model_validate(
        {
            "story_id": str(STORY_ID),
            "story_version": 2,
            "title_context_en": "Arsenal bid for Vinicius",
            "claims": [
                {
                    "claim_id": str(CLAIM_ID),
                    "statement_en": "Arsenal submitted a bid.",
                    "source_article_ids": [str(SOURCE_ID)],
                }
            ],
            "source_article_ids": [str(SOURCE_ID)],
            "prompt_version": "story-article-v1",
        }
    )


def test_mock_provider_generates_only_from_input_claims() -> None:
    result = MockStoryArticleGenerationProvider().generate(request())

    assert result.story_id == STORY_ID
    assert result.story_version == 2
    assert result.used_claim_ids == (CLAIM_ID,)
    assert result.used_source_article_ids == (SOURCE_ID,)
    assert "Arsenal submitted a bid." in result.body_en
