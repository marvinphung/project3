from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid5

from footballpulse_intelligence_service.domain.entity import EntityType, normalize_alias
from footballpulse_intelligence_service.domain.extraction import SourceField, SpanPrediction

_UNRESOLVED_NAMESPACE = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c9991")


class UnresolvedReviewStatus(StrEnum):
    PENDING_REVIEW = "PENDING_REVIEW"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class UnresolvedEntityMention:
    id: UUID
    article_version_id: UUID
    source_field: SourceField
    mention_text: str
    normalized_alias: str
    predicted_type: EntityType
    start: int
    end: int
    score: float
    model_name: str
    model_version: str
    status: UnresolvedReviewStatus
    created_at: datetime

    @classmethod
    def from_prediction(
        cls,
        *,
        article_version_id: UUID,
        prediction: SpanPrediction,
        predicted_type: EntityType,
        model_name: str,
        model_version: str,
        now: datetime,
    ) -> UnresolvedEntityMention:
        if now.tzinfo is None:
            raise ValueError("unresolved mention timestamp must be timezone-aware")
        model_name = model_name.strip()
        model_version = model_version.strip()
        if not model_name or not model_version:
            raise ValueError("unresolved mention requires model identity")
        if len(model_name) > 200 or len(model_version) > 100:
            raise ValueError("unresolved mention model identity exceeds storage limits")
        if len(prediction.text) > 200:
            raise ValueError("unresolved mention text exceeds storage limit")
        normalized = normalize_alias(prediction.text)
        if not normalized:
            raise ValueError("unresolved mention must be normalizable")
        if len(normalized) > 200:
            raise ValueError("unresolved normalized alias exceeds storage limit")
        stable_key = ":".join(
            (
                str(article_version_id),
                prediction.source_field.value,
                str(prediction.start),
                str(prediction.end),
                predicted_type.value,
                model_name,
                model_version,
            )
        )
        return cls(
            uuid5(_UNRESOLVED_NAMESPACE, stable_key),
            article_version_id,
            prediction.source_field,
            prediction.text,
            normalized,
            predicted_type,
            prediction.start,
            prediction.end,
            prediction.score,
            model_name,
            model_version,
            UnresolvedReviewStatus.PENDING_REVIEW,
            now,
        )
