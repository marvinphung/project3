from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from footballpulse_intelligence_service.domain.entity import Entity, EntityType, normalize_alias
from footballpulse_intelligence_service.domain.extraction import (
    EntityLabel,
    SourceField,
    SpanPrediction,
    deduplicate_predictions,
    split_text,
)
from footballpulse_intelligence_service.domain.unresolved import UnresolvedEntityMention

_LABEL_TYPES = {
    EntityLabel.PLAYER: EntityType.PLAYER,
    EntityLabel.CLUB: EntityType.CLUB,
    EntityLabel.COACH: EntityType.COACH,
    EntityLabel.COMPETITION: EntityType.COMPETITION,
}
DEFAULT_LABELS = tuple(EntityLabel)


@dataclass(frozen=True, slots=True)
class ModelSpan:
    text: str
    label: EntityLabel
    start: int
    end: int
    score: float


class EntityExtractor(Protocol):
    model_name: str
    model_version: str

    def extract(
        self,
        text: str,
        *,
        labels: tuple[EntityLabel, ...],
        threshold: float,
    ) -> list[ModelSpan]: ...


class EntityResolver(Protocol):
    def resolve(self, alias: str) -> Entity | None: ...


class UnresolvedMentionRepository(Protocol):
    def add_once(self, mention: UnresolvedEntityMention) -> UnresolvedEntityMention: ...


class ResolutionStatus(StrEnum):
    RESOLVED = "RESOLVED"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True, slots=True)
class ExtractionRequest:
    article_version_id: UUID
    title: str
    cleaned_content: str


@dataclass(frozen=True, slots=True)
class ResolvedMention:
    prediction: SpanPrediction
    status: ResolutionStatus
    entity_id: UUID | None


@dataclass(frozen=True, slots=True)
class EntityExtractionResult:
    article_version_id: UUID
    mentions: tuple[ResolvedMention, ...]
    model_name: str
    model_version: str
    detection_threshold: float
    review_threshold: float


class EntityExtractionPipeline:
    def __init__(
        self,
        *,
        extractor: EntityExtractor,
        resolver: EntityResolver,
        unresolved_repository: UnresolvedMentionRepository,
        clock: Callable[[], datetime],
        detection_threshold: float = 0.5,
        review_threshold: float = 0.75,
        max_words_per_chunk: int = 300,
        overlap_words: int = 40,
        max_chunks_per_field: int = 64,
        max_mentions: int = 500,
    ) -> None:
        if not 0 <= detection_threshold <= review_threshold <= 1:
            raise ValueError("entity thresholds must satisfy 0 <= detection <= review <= 1")
        if max_mentions < 1:
            raise ValueError("max mentions must be positive")
        self._extractor = extractor
        self._resolver = resolver
        self._unresolved_repository = unresolved_repository
        self._clock = clock
        self._detection_threshold = detection_threshold
        self._review_threshold = review_threshold
        self._max_words = max_words_per_chunk
        self._overlap_words = overlap_words
        self._max_chunks = max_chunks_per_field
        self._max_mentions = max_mentions

    def process(self, request: ExtractionRequest) -> EntityExtractionResult:
        predictions = deduplicate_predictions(
            self._extract_field(SourceField.TITLE, request.title)
            + self._extract_field(SourceField.CONTENT, request.cleaned_content)
        )
        if len(predictions) > self._max_mentions:
            raise ValueError("entity prediction count exceeds configured limit")

        resolved_mentions: list[ResolvedMention] = []
        observed_at = self._clock()
        for prediction in predictions:
            predicted_type = _LABEL_TYPES[prediction.label]
            entity = self._resolver.resolve(normalize_alias(prediction.text))
            is_match = entity is not None and entity.entity_type is predicted_type
            if is_match and entity is not None:
                resolved_mentions.append(
                    ResolvedMention(prediction, ResolutionStatus.RESOLVED, entity.id)
                )
                continue

            resolved_mentions.append(ResolvedMention(prediction, ResolutionStatus.UNRESOLVED, None))
            if prediction.score >= self._review_threshold:
                self._unresolved_repository.add_once(
                    UnresolvedEntityMention.from_prediction(
                        article_version_id=request.article_version_id,
                        prediction=prediction,
                        predicted_type=predicted_type,
                        model_name=self._extractor.model_name,
                        model_version=self._extractor.model_version,
                        now=observed_at,
                    )
                )

        return EntityExtractionResult(
            request.article_version_id,
            tuple(resolved_mentions),
            self._extractor.model_name,
            self._extractor.model_version,
            self._detection_threshold,
            self._review_threshold,
        )

    def _extract_field(self, source_field: SourceField, text: str) -> list[SpanPrediction]:
        predictions: list[SpanPrediction] = []
        for chunk in split_text(
            text,
            max_words=self._max_words,
            overlap_words=self._overlap_words,
            max_chunks=self._max_chunks,
        ):
            spans = self._extractor.extract(
                chunk.text,
                labels=DEFAULT_LABELS,
                threshold=self._detection_threshold,
            )
            for span in spans:
                if span.start < 0 or span.end > len(chunk.text) or span.end <= span.start:
                    raise ValueError("model returned invalid local offsets")
                if chunk.text[span.start : span.end] != span.text:
                    raise ValueError("model span text does not match its offsets")
                predictions.append(
                    SpanPrediction.create(
                        source_field=source_field,
                        source_text=text,
                        label=span.label,
                        start=chunk.start + span.start,
                        end=chunk.start + span.end,
                        score=span.score,
                    )
                )
                if len(predictions) > self._max_mentions:
                    raise ValueError("entity prediction count exceeds configured limit")
        return predictions
