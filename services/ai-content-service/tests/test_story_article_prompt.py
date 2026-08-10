from __future__ import annotations

from uuid import UUID

from footballpulse_ai_content_service.contracts.generation import (
    GroundedStoryClaim,
    StoryArticleGenerationInput,
)
from footballpulse_ai_content_service.prompts.story_article import (
    STORY_ARTICLE_PROMPT_VERSION,
    build_story_article_prompt,
)


def test_prompt_builder_is_versioned_and_contains_only_grounded_context() -> None:
    source = StoryArticleGenerationInput(
        story_id=UUID(int=1),
        story_version=2,
        title_context_en="Arsenal bid",
        claims=(
            GroundedStoryClaim(
                claim_id=UUID(int=2),
                statement_en="Arsenal submitted a bid.",
                source_article_ids=(UUID(int=3),),
            ),
        ),
        source_article_ids=(UUID(int=3),),
        prompt_version=STORY_ARTICLE_PROMPT_VERSION,
    )

    prompt = build_story_article_prompt(source)

    assert prompt.prompt_version == STORY_ARTICLE_PROMPT_VERSION
    assert "Arsenal submitted a bid." in prompt.user_message
    assert "Do not invent" in prompt.system_message
    assert str(UUID(int=2)) in prompt.user_message
