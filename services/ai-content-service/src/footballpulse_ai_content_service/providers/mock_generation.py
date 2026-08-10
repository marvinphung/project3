from __future__ import annotations

from footballpulse_ai_content_service.contracts.generation import (
    GeneratedStoryArticle,
    StoryArticleGenerationInput,
)
from footballpulse_ai_content_service.providers.base import ProviderName


class MockStoryArticleGenerationProvider:
    name = ProviderName.MOCK

    def generate(self, source: StoryArticleGenerationInput) -> GeneratedStoryArticle:
        body_en = " ".join(claim.statement_en for claim in source.claims)
        body_vi = "Tóm tắt theo dữ liệu đã xác thực: " + body_en
        return GeneratedStoryArticle(
            story_id=source.story_id,
            story_version=source.story_version,
            title_en=source.title_context_en,
            body_en=body_en,
            title_vi="Tổng hợp: " + source.title_context_en,
            body_vi=body_vi,
            used_claim_ids=tuple(claim.claim_id for claim in source.claims),
            used_source_article_ids=tuple(
                dict.fromkeys(
                    source_id
                    for claim in source.claims
                    for source_id in claim.source_article_ids
                )
            ),
            model_version="mock-story-generator-v1",
            prompt_version=source.prompt_version,
        )
