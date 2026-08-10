from __future__ import annotations

from typing import Protocol

from footballpulse_ai_content_service.contracts.generation import (
    GeneratedStoryArticle,
    StoryArticleGenerationInput,
)


class StoryArticleGenerationProvider(Protocol):
    def generate(self, source: StoryArticleGenerationInput) -> GeneratedStoryArticle: ...
