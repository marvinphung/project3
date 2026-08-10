from __future__ import annotations

from uuid import UUID

import pytest
from footballpulse_ai_content_service.contracts.generation import (
    GeneratedStoryArticle,
    GroundedStoryClaim,
    StoryArticleGenerationInput,
)
from pydantic import ValidationError

STORY_ID = UUID(int=1)
CLAIM_ID = UUID(int=2)
SOURCE_ID = UUID(int=3)


def generation_input() -> StoryArticleGenerationInput:
    return StoryArticleGenerationInput(
        story_id=STORY_ID,
        story_version=4,
        title_context_en="Arsenal bid for Vinicius Junior",
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


def test_generation_contract_accepts_grounded_bilingual_article() -> None:
    result = GeneratedStoryArticle(
        story_id=STORY_ID,
        story_version=4,
        title_en="Arsenal bid for Vinicius Junior",
        body_en="Arsenal submitted a bid.",
        title_vi="Arsenal hỏi mua Vinicius Junior",
        body_vi="Arsenal đã gửi đề nghị.",
        used_claim_ids=(CLAIM_ID,),
        used_source_article_ids=(SOURCE_ID,),
        model_version="qwen3-8b",
        prompt_version="story-article-v1",
    )

    assert result.story_id == STORY_ID


def test_generation_input_rejects_claim_source_outside_story_context() -> None:
    with pytest.raises(ValidationError, match="outside generation input"):
        StoryArticleGenerationInput(
            story_id=STORY_ID,
            story_version=1,
            title_context_en="Story",
            claims=(
                GroundedStoryClaim(
                    claim_id=CLAIM_ID,
                    statement_en="Claim",
                    source_article_ids=(UUID(int=99),),
                ),
            ),
            source_article_ids=(SOURCE_ID,),
            prompt_version="v1",
        )


def test_generated_article_rejects_duplicate_grounding_ids() -> None:
    with pytest.raises(ValidationError, match="claim IDs must be unique"):
        GeneratedStoryArticle(
            story_id=STORY_ID,
            story_version=1,
            title_en="Title",
            body_en="Body",
            title_vi="Tiêu đề",
            body_vi="Nội dung",
            used_claim_ids=(CLAIM_ID, CLAIM_ID),
            used_source_article_ids=(SOURCE_ID,),
            model_version="mock",
            prompt_version="v1",
        )
