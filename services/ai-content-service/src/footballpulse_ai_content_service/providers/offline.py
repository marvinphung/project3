from __future__ import annotations

import re

from footballpulse_ai_content_service.contracts.batch import BatchRecord, SuccessfulBatchRecord
from footballpulse_ai_content_service.contracts.enrichment import (
    ArticleEnrichmentInput,
    ArticleEnrichmentOutput,
    EventType,
)
from footballpulse_ai_content_service.providers.base import ProviderName


class DeterministicOfflineProvider:
    """A zero-dependency provider for local development and smoke runs.

    It deliberately does not pretend to understand the article.  It produces a
    grounded, deterministic excerpt so the rest of the pipeline (batch state,
    persistence and API contracts) can be exercised without downloading a model.
    """

    name = ProviderName.MOCK

    def enrich(self, inputs: tuple[ArticleEnrichmentInput, ...]) -> tuple[BatchRecord, ...]:
        records: list[BatchRecord] = []
        for source in inputs:
            text = re.sub(r"\s+", " ", source.cleaned_content).strip()
            summary = text[:3_800] or source.title
            records.append(
                SuccessfulBatchRecord(
                    article_version_id=source.article_version_id,
                    status="SUCCESS",
                    result=ArticleEnrichmentOutput(
                        contract_version="article-enrichment.v1",
                        article_version_id=source.article_version_id,
                        input_hash=source.input_hash,
                        event_type=EventType.OTHER,
                        summary_en=summary,
                        claims=(),
                        model_version="offline-deterministic-v1",
                        prompt_version="offline-excerpt-v1",
                    ),
                )
            )
        return tuple(records)
