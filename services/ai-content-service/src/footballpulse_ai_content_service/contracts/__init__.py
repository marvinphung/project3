"""Strict AI input and output contracts."""

from footballpulse_ai_content_service.contracts.enrichment import (
    ArticleEnrichmentInput,
    ArticleEnrichmentOutput,
    ClaimOutput,
)
from footballpulse_ai_content_service.contracts.generation import (
    GeneratedStoryArticle,
    GroundedStoryClaim,
    StoryArticleGenerationInput,
)

__all__ = [
    "ArticleEnrichmentInput",
    "ArticleEnrichmentOutput",
    "ClaimOutput",
    "GeneratedStoryArticle",
    "GroundedStoryClaim",
    "StoryArticleGenerationInput",
]
