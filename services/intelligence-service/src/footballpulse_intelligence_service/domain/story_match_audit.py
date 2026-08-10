from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid5

from footballpulse_intelligence_service.domain.story_candidate_decision import (
    CandidateDecisionInput,
    MatchAction,
    StoryMatchDecision,
)

_AUDIT_NAMESPACE = UUID("018f8b45-b634-7c81-a47d-9a7c2f3ca003")
_SCORE_QUANTUM = Decimal("0.001")


def _decimal(value: float) -> Decimal:
    return Decimal(str(value)).quantize(_SCORE_QUANTUM)


def _reasons(values: tuple[str, ...]) -> tuple[str, ...]:
    result = tuple(" ".join(value.split()) for value in values)
    if not result or any(not value or len(value) > 100 for value in result):
        raise ValueError("audit reason codes are invalid")
    return result


@dataclass(frozen=True, slots=True)
class StoryMatchAuditScoreComponents:
    vector_similarity: Decimal
    primary_entity: Decimal
    entity_overlap: Decimal
    predicate_compatibility: Decimal
    time_distance: Decimal


@dataclass(frozen=True, slots=True)
class StoryMatchAuditCandidate:
    id: UUID
    decision_id: UUID
    rank: int
    story_id: UUID
    story_version: int
    total_score: Decimal
    components: StoryMatchAuditScoreComponents
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StoryMatchAuditRecord:
    id: UUID
    article_version_id: UUID
    input_hash: str
    candidate_set_hash: str
    action: MatchAction
    selected_story_id: UUID | None
    selected_story_version: int | None
    review_threshold: Decimal
    attach_threshold: Decimal
    near_tie_margin: Decimal
    matcher_version: str
    embedding_model_name: str
    embedding_model_version: str
    reason_codes: tuple[str, ...]
    candidates: tuple[StoryMatchAuditCandidate, ...]
    created_at: datetime

    @classmethod
    def create(
        cls,
        *,
        article_version_id: UUID,
        input_hash: str,
        decision: StoryMatchDecision,
        now: datetime,
    ) -> StoryMatchAuditRecord:
        if len(input_hash) != 64 or any(char not in "0123456789abcdef" for char in input_hash):
            raise ValueError("audit input hash must be lowercase SHA-256")
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("audit created_at must be timezone-aware")
        review_threshold = _decimal(decision.review_threshold)
        attach_threshold = _decimal(decision.attach_threshold)
        near_tie_margin = _decimal(decision.near_tie_margin)
        candidate_identity = [
            {
                "rank": rank,
                "story_id": str(candidate.story_id),
                "story_version": candidate.story_version,
                "total": str(_decimal(candidate.score.total)),
            }
            for rank, candidate in enumerate(decision.ranked_candidates, start=1)
        ]
        candidate_set_hash = hashlib.sha256(
            json.dumps(candidate_identity, separators=(",", ":"), sort_keys=True).encode()
        ).hexdigest()
        stable_key = ":".join(
            (
                str(article_version_id),
                input_hash,
                candidate_set_hash,
                decision.matcher_version,
                decision.embedding_model_name,
                decision.embedding_model_version,
                str(review_threshold),
                str(attach_threshold),
                str(near_tie_margin),
            )
        )
        decision_id = uuid5(_AUDIT_NAMESPACE, stable_key)
        candidates = tuple(
            _candidate(decision_id, rank, candidate)
            for rank, candidate in enumerate(decision.ranked_candidates, start=1)
        )
        return cls(
            decision_id,
            article_version_id,
            input_hash,
            candidate_set_hash,
            MatchAction(decision.action),
            decision.selected_story_id,
            decision.selected_story_version,
            review_threshold,
            attach_threshold,
            near_tie_margin,
            decision.matcher_version,
            decision.embedding_model_name,
            decision.embedding_model_version,
            _reasons(decision.reason_codes),
            candidates,
            now,
        )


def _candidate(
    decision_id: UUID,
    rank: int,
    source: CandidateDecisionInput,
) -> StoryMatchAuditCandidate:
    raw = source.score.components
    components = StoryMatchAuditScoreComponents(
        _decimal(raw.vector_similarity),
        _decimal(raw.primary_entity),
        _decimal(raw.entity_overlap),
        _decimal(raw.predicate_compatibility),
        _decimal(raw.time_distance),
    )
    total = sum(
        (
            components.vector_similarity,
            components.primary_entity,
            components.entity_overlap,
            components.predicate_compatibility,
            components.time_distance,
        ),
        Decimal("0.000"),
    )
    candidate_id = uuid5(_AUDIT_NAMESPACE, f"{decision_id}:candidate:{rank}:{source.story_id}")
    return StoryMatchAuditCandidate(
        candidate_id,
        decision_id,
        rank,
        source.story_id,
        source.story_version,
        total,
        components,
        _reasons(source.score.reason_codes),
    )
