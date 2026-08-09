from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from footballpulse_ai_content_service.batch.coordinator import (
    EnrichmentResultSink,
    GroundedEnrichment,
)
from footballpulse_ai_content_service.contracts.batch import (
    BatchRecord,
    FailedBatchRecord,
    SuccessfulBatchRecord,
)
from footballpulse_ai_content_service.contracts.enrichment import ArticleEnrichmentInput
from footballpulse_ai_content_service.providers.base import EnrichmentProvider
from footballpulse_ai_content_service.validation.grounding import GroundingValidator


class ProviderEnrichmentService:
    def __init__(
        self,
        *,
        provider: EnrichmentProvider,
        sink: EnrichmentResultSink,
        clock: Callable[[], datetime],
    ) -> None:
        self._provider = provider
        self._sink = sink
        self._clock = clock
        self._grounding = GroundingValidator()

    def enrich(self, inputs: tuple[ArticleEnrichmentInput, ...]) -> tuple[BatchRecord, ...]:
        records = self._provider.enrich(inputs)
        sources = {source.article_version_id: source for source in inputs}
        if len(sources) != len(inputs):
            raise ValueError("provider input contains duplicate article identity")
        if len(records) != len(inputs):
            raise ValueError("provider must return exactly one record per article input")

        seen: set[object] = set()
        grounded: list[GroundedEnrichment] = []
        for record in records:
            article_id = record.article_version_id
            if article_id in seen:
                raise ValueError("provider returned duplicate article identity")
            seen.add(article_id)
            source = sources.get(article_id)
            if source is None:
                raise ValueError("provider record article is not present in input batch")
            record_hash = self._input_hash(record)
            if record_hash != source.input_hash:
                raise ValueError("provider record input_hash does not match input batch")
            if isinstance(record, SuccessfulBatchRecord):
                grounded.append(
                    GroundedEnrichment(
                        output=record.result,
                        validation=self._grounding.validate(source, record.result),
                        validated_at=self._clock(),
                    )
                )
        if seen != set(sources):
            raise ValueError("provider omitted an article input")
        self._sink.persist(tuple(grounded))
        return records

    @staticmethod
    def _input_hash(record: BatchRecord) -> str:
        if isinstance(record, SuccessfulBatchRecord):
            return record.result.input_hash
        if isinstance(record, FailedBatchRecord):
            return record.input_hash
        raise TypeError("unsupported provider batch record")
