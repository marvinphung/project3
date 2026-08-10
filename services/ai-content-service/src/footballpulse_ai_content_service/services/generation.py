from __future__ import annotations

from footballpulse_ai_content_service.contracts.generation import (
    GeneratedStoryArticle,
    StoryArticleGenerationInput,
)
from footballpulse_ai_content_service.providers.base import FallbackReason, ProviderFailure
from footballpulse_ai_content_service.providers.generation import StoryArticleGenerationProvider


class GroundedArticleGenerationService:
    def __init__(self, provider: StoryArticleGenerationProvider) -> None:
        self._provider = provider

    def generate(self, source: StoryArticleGenerationInput) -> GeneratedStoryArticle:
        output = self._provider.generate(source)
        if output.story_id != source.story_id or output.story_version != source.story_version:
            raise ProviderFailure(
                FallbackReason.OUTPUT_GROUNDING,
                "generated article Story identity does not match input",
            )
        allowed_claims = {claim.claim_id for claim in source.claims}
        allowed_sources = set(source.source_article_ids)
        if not set(output.used_claim_ids) <= allowed_claims:
            raise ProviderFailure(
                FallbackReason.OUTPUT_GROUNDING,
                "generated article references a claim outside input",
            )
        if not set(output.used_source_article_ids) <= allowed_sources:
            raise ProviderFailure(
                FallbackReason.OUTPUT_GROUNDING,
                "generated article references a source outside input",
            )
        return output
