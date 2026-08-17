from __future__ import annotations

import logging
import time

from footballpulse_runtime_config import bind_log_context, log_event

from footballpulse_ai_content_service.contracts.generation import (
    GeneratedStoryArticle,
    StoryArticleGenerationInput,
)
from footballpulse_ai_content_service.providers.base import FallbackReason, ProviderFailure
from footballpulse_ai_content_service.providers.generation import StoryArticleGenerationProvider

LOGGER = logging.getLogger("footballpulse.ai.story_generation")


class GroundedArticleGenerationService:
    def __init__(self, provider: StoryArticleGenerationProvider) -> None:
        self._provider = provider

    def generate(self, source: StoryArticleGenerationInput) -> GeneratedStoryArticle:
        started = time.monotonic()
        with bind_log_context(correlation_id=str(source.story_id)):
            log_event(
                LOGGER,
                "story_generation_started",
                story_id=str(source.story_id),
                story_version=source.story_version,
                claim_count=len(source.claims),
                source_count=len(source.source_article_ids),
            )
            try:
                output = self._provider.generate(source)
            except Exception as error:
                log_event(
                    LOGGER,
                    "story_generation_failed",
                    level=logging.ERROR,
                    error=error,
                    story_id=str(source.story_id),
                    duration_ms=round((time.monotonic() - started) * 1000),
                )
                raise
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
        log_event(
            LOGGER,
            "story_generation_completed",
            story_id=str(source.story_id),
            story_version=source.story_version,
            used_claim_count=len(output.used_claim_ids),
            used_source_count=len(output.used_source_article_ids),
            duration_ms=round((time.monotonic() - started) * 1000),
        )
        return output
