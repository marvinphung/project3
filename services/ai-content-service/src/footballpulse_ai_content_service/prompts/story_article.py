from __future__ import annotations

from dataclasses import dataclass

from footballpulse_ai_content_service.contracts.generation import StoryArticleGenerationInput

STORY_ARTICLE_PROMPT_VERSION = "story-article-v1"


@dataclass(frozen=True, slots=True)
class StoryArticlePrompt:
    prompt_version: str
    system_message: str
    user_message: str


def build_story_article_prompt(source: StoryArticleGenerationInput) -> StoryArticlePrompt:
    if source.prompt_version != STORY_ARTICLE_PROMPT_VERSION:
        raise ValueError("unsupported Story article prompt version")
    claim_lines = "\n".join(
        f"- claim_id={claim.claim_id}; sources={','.join(map(str, claim.source_article_ids))}; "
        f"statement={claim.statement_en}"
        for claim in source.claims
    )
    system_message = (
        "Write a concise grounded football article in English and Vietnamese. "
        "Use only the supplied claims and source IDs. Do not invent, infer, or "
        "strengthen facts. Preserve uncertainty and cite used claim IDs."
    )
    user_message = (
        f"Story title context: {source.title_context_en}\n"
        f"Story version: {source.story_version}\n"
        "Grounded claims:\n"
        f"{claim_lines}\n"
        "Return structured bilingual output with title/body and used IDs."
    )
    return StoryArticlePrompt(STORY_ARTICLE_PROMPT_VERSION, system_message, user_message)
