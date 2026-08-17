from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from footballpulse_runtime_config import bind_log_context, log_event

from footballpulse_intelligence_service.application.entity_extraction import (
    EntityExtractionResult,
    ExtractionRequest,
    ResolutionStatus,
)
from footballpulse_intelligence_service.domain.embedding import EmbeddingInput, EmbeddingRecord
from footballpulse_intelligence_service.domain.entity import Entity, EntityType

LOGGER = logging.getLogger("footballpulse.intelligence.preprocessing")


@dataclass(frozen=True, slots=True)
class SourceArticle:
    article_version_id: UUID
    title: str
    cleaned_content: str


@dataclass(frozen=True, slots=True)
class CanonicalEntityReference:
    entity_id: UUID
    entity_type: EntityType
    canonical_name: str


@dataclass(frozen=True, slots=True)
class ArticleIntelligenceResult:
    article_version_id: UUID
    status: str
    canonical_entities: tuple[CanonicalEntityReference, ...]
    entity_model_name: str | None
    entity_model_version: str | None
    embedding_id: UUID | None
    embedding_input_hash: str | None
    error_type: str | None
    processed_at: datetime

    @classmethod
    def failed(
        cls, article_version_id: UUID, *, error_type: str, processed_at: datetime
    ) -> ArticleIntelligenceResult:
        return cls(
            article_version_id,
            "FAILED",
            (),
            None,
            None,
            None,
            None,
            error_type,
            processed_at,
        )


@dataclass(frozen=True, slots=True)
class PreprocessingReport:
    claimed: int
    completed: int
    failed: int


class SourceArticleRepository(Protocol):
    def claim_pending(self, *, limit: int) -> list[SourceArticle]: ...

    def save_result(self, result: ArticleIntelligenceResult) -> None: ...


class ExtractionPipeline(Protocol):
    def process(self, request: ExtractionRequest) -> EntityExtractionResult: ...


class ArticleEmbeddingPipeline(Protocol):
    def process_batch(self, items: list[EmbeddingInput]) -> tuple[EmbeddingRecord, ...]: ...


class ArticlePreprocessingWorker:
    def __init__(
        self,
        *,
        source_repository: SourceArticleRepository,
        extraction_pipeline: ExtractionPipeline,
        embedding_pipeline: ArticleEmbeddingPipeline,
        entity_lookup: Callable[[UUID], Entity | None],
        clock: Callable[[], datetime],
    ) -> None:
        self._source_repository = source_repository
        self._extraction_pipeline = extraction_pipeline
        self._embedding_pipeline = embedding_pipeline
        self._entity_lookup = entity_lookup
        self._clock = clock

    def run_once(self, *, limit: int = 50) -> PreprocessingReport:
        if not 1 <= limit <= 256:
            raise ValueError("preprocessing limit must be between 1 and 256")
        articles = self._source_repository.claim_pending(limit=limit)
        log_event(
            LOGGER,
            "intelligence_batch_claimed" if articles else "intelligence_batch_empty",
            claimed=len(articles),
            limit=limit,
        )
        completed = 0
        failed = 0
        for article in articles:
            started = time.monotonic()
            with bind_log_context(correlation_id=str(article.article_version_id)):
                log_event(
                    LOGGER,
                    "article_intelligence_started",
                    article_version_id=str(article.article_version_id),
                    content_chars=len(article.cleaned_content),
                )
            try:
                self._process_article(article)
                completed += 1
            except Exception as error:
                self._source_repository.save_result(
                    ArticleIntelligenceResult.failed(
                        article.article_version_id,
                        error_type=type(error).__name__,
                        processed_at=self._clock(),
                    )
                )
                failed += 1
                log_event(
                    LOGGER,
                    "article_intelligence_failed",
                    level=logging.ERROR,
                    error=error,
                    article_version_id=str(article.article_version_id),
                    duration_ms=round((time.monotonic() - started) * 1000),
                )
            else:
                log_event(
                    LOGGER,
                    "article_intelligence_completed",
                    article_version_id=str(article.article_version_id),
                    duration_ms=round((time.monotonic() - started) * 1000),
                )
        return PreprocessingReport(len(articles), completed, failed)

    def _process_article(self, article: SourceArticle) -> None:
        extraction = self._extraction_pipeline.process(
            ExtractionRequest(
                article.article_version_id,
                article.title,
                article.cleaned_content,
            )
        )
        log_event(
            LOGGER,
            "entity_extraction_completed",
            article_version_id=str(article.article_version_id),
            model_name=extraction.model_name,
            model_version=extraction.model_version,
            mention_count=len(extraction.mentions),
            resolved_count=sum(
                mention.status is ResolutionStatus.RESOLVED for mention in extraction.mentions
            ),
        )
        entities_by_id: dict[UUID, Entity] = {}
        for mention in extraction.mentions:
            if mention.status is not ResolutionStatus.RESOLVED or mention.entity_id is None:
                continue
            entity = self._entity_lookup(mention.entity_id)
            if entity is None or not entity.is_active:
                raise ValueError("resolved entity is missing or inactive")
            entities_by_id[entity.id] = entity
        entities = tuple(
            sorted(
                entities_by_id.values(),
                key=lambda item: (item.entity_type, item.canonical_name),
            )
        )
        embeddings = self._embedding_pipeline.process_batch(
            [
                EmbeddingInput(
                    article.article_version_id,
                    article.title,
                    tuple(entity.canonical_name for entity in entities),
                    article.cleaned_content,
                )
            ]
        )
        if len(embeddings) != 1:
            raise ValueError("embedding pipeline returned an unexpected result count")
        embedding = embeddings[0]
        log_event(
            LOGGER,
            "embedding_completed",
            article_version_id=str(article.article_version_id),
            embedding_id=str(embedding.id),
            entity_count=len(entities),
        )
        self._source_repository.save_result(
            ArticleIntelligenceResult(
                article.article_version_id,
                "COMPLETED",
                tuple(
                    CanonicalEntityReference(entity.id, entity.entity_type, entity.canonical_name)
                    for entity in entities
                ),
                extraction.model_name,
                extraction.model_version,
                embedding.id,
                embedding.input_hash,
                None,
                self._clock(),
            )
        )
