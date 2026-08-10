from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from footballpulse_intelligence_service.domain.story import (
    ClaimPredicate,
    StoryEventType,
)

_EVENT_WINDOWS = {
    StoryEventType.MATCH: timedelta(days=3),
    StoryEventType.INJURY: timedelta(days=21),
    StoryEventType.DISCIPLINARY: timedelta(days=14),
    StoryEventType.TRANSFER: timedelta(days=30),
    StoryEventType.CONTRACT: timedelta(days=30),
    StoryEventType.MANAGERIAL: timedelta(days=30),
    StoryEventType.OTHER: timedelta(days=7),
}

_PREDICATE_SUCCESSORS = {
    ClaimPredicate.EXPRESSED_INTEREST: frozenset(
        {
            ClaimPredicate.CONTACTED,
            ClaimPredicate.SUBMITTED_BID,
            ClaimPredicate.ACCEPTED_BID,
            ClaimPredicate.REJECTED_BID,
            ClaimPredicate.COMPLETED_TRANSFER,
        }
    ),
    ClaimPredicate.CONTACTED: frozenset(
        {
            ClaimPredicate.SUBMITTED_BID,
            ClaimPredicate.ACCEPTED_BID,
            ClaimPredicate.REJECTED_BID,
            ClaimPredicate.COMPLETED_TRANSFER,
        }
    ),
    ClaimPredicate.SUBMITTED_BID: frozenset(
        {
            ClaimPredicate.ACCEPTED_BID,
            ClaimPredicate.REJECTED_BID,
            ClaimPredicate.COMPLETED_TRANSFER,
        }
    ),
    ClaimPredicate.ACCEPTED_BID: frozenset({ClaimPredicate.COMPLETED_TRANSFER}),
    ClaimPredicate.NEGOTIATING_CONTRACT: frozenset({ClaimPredicate.SIGNED_CONTRACT}),
    ClaimPredicate.SUFFERED_INJURY: frozenset({ClaimPredicate.EXPECTED_RETURN}),
    ClaimPredicate.MATCH_SCHEDULED: frozenset({ClaimPredicate.MATCH_RESULT}),
}


def story_event_window(event_type: StoryEventType) -> timedelta:
    return _EVENT_WINDOWS[StoryEventType(event_type)]


@dataclass(frozen=True, slots=True)
class StoryCandidateScoreInput:
    event_type: StoryEventType
    cosine_similarity: float
    query_primary_entity_ids: tuple[UUID, ...]
    candidate_primary_entity_ids: tuple[UUID, ...]
    query_entity_ids: tuple[UUID, ...]
    candidate_entity_ids: tuple[UUID, ...]
    query_predicates: tuple[ClaimPredicate, ...]
    candidate_predicates: tuple[ClaimPredicate, ...]
    observed_at: datetime
    candidate_last_seen_at: datetime


@dataclass(frozen=True, slots=True)
class StoryCandidateScoreComponents:
    vector_similarity: float
    primary_entity: float
    entity_overlap: float
    predicate_compatibility: float
    time_distance: float


@dataclass(frozen=True, slots=True)
class StoryCandidateScore:
    total: float
    components: StoryCandidateScoreComponents
    reason_codes: tuple[str, ...]


def _unique(values: tuple[UUID, ...], field: str) -> frozenset[UUID]:
    result = frozenset(values)
    if len(result) != len(values):
        raise ValueError(f"{field} must contain unique IDs")
    return result


def _primary_score(
    query: frozenset[UUID], candidate: frozenset[UUID]
) -> tuple[float, str]:
    if not query:
        return 0.0, "QUERY_PRIMARY_ENTITY_MISSING"
    if not candidate:
        return 0.0, "CANDIDATE_PRIMARY_ENTITY_MISSING"
    if query != candidate:
        return 0.0, "PRIMARY_ENTITY_CONFLICT"
    return 25.0, "PRIMARY_ENTITY_MATCH"


def _entity_overlap_score(
    query_entities: frozenset[UUID],
    candidate_entities: frozenset[UUID],
    query_primary: frozenset[UUID],
    candidate_primary: frozenset[UUID],
) -> tuple[float, str]:
    query_secondary = query_entities - query_primary
    candidate_secondary = candidate_entities - candidate_primary
    if not query_secondary:
        return 0.0, "NO_QUERY_SECONDARY_ENTITIES"
    ratio = len(query_secondary & candidate_secondary) / len(query_secondary)
    if ratio == 1:
        reason = "SECONDARY_ENTITY_FULL_OVERLAP"
    elif ratio > 0:
        reason = "SECONDARY_ENTITY_PARTIAL_OVERLAP"
    else:
        reason = "NO_SECONDARY_ENTITY_OVERLAP"
    return 15.0 * ratio, reason


def _predicate_score(
    query: frozenset[ClaimPredicate], candidate: frozenset[ClaimPredicate]
) -> tuple[float, str]:
    if query & candidate:
        return 20.0, "PREDICATE_EXACT_MATCH"
    if ClaimPredicate.DENIED_REPORT in query and candidate:
        return 20.0, "PREDICATE_PROGRESSION"
    if any(
        incoming in _PREDICATE_SUCCESSORS.get(existing, ())
        for existing in candidate
        for incoming in query
    ):
        return 20.0, "PREDICATE_PROGRESSION"
    return 0.0, "PREDICATE_CONFLICT"


def score_story_candidate(source: StoryCandidateScoreInput) -> StoryCandidateScore:
    event_type = StoryEventType(source.event_type)
    if not math.isfinite(source.cosine_similarity) or not -1 <= source.cosine_similarity <= 1:
        raise ValueError("cosine_similarity must be finite and between -1 and 1")
    if source.observed_at.tzinfo is None or source.observed_at.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")
    if (
        source.candidate_last_seen_at.tzinfo is None
        or source.candidate_last_seen_at.utcoffset() is None
    ):
        raise ValueError("candidate_last_seen_at must be timezone-aware")
    if source.observed_at < source.candidate_last_seen_at:
        raise ValueError("observed_at cannot be before candidate_last_seen_at")

    query_primary = _unique(source.query_primary_entity_ids, "query_primary_entity_ids")
    candidate_primary = _unique(
        source.candidate_primary_entity_ids, "candidate_primary_entity_ids"
    )
    query_entities = _unique(source.query_entity_ids, "query_entity_ids")
    candidate_entities = _unique(source.candidate_entity_ids, "candidate_entity_ids")
    query_predicates = frozenset(ClaimPredicate(value) for value in source.query_predicates)
    candidate_predicates = frozenset(
        ClaimPredicate(value) for value in source.candidate_predicates
    )
    if not query_predicates or not candidate_predicates:
        raise ValueError("candidate scoring requires query and candidate predicates")

    vector_score = 30.0 * max(0.0, source.cosine_similarity)
    primary_score, primary_reason = _primary_score(query_primary, candidate_primary)
    overlap_score, overlap_reason = _entity_overlap_score(
        query_entities,
        candidate_entities,
        query_primary,
        candidate_primary,
    )
    predicate_score, predicate_reason = _predicate_score(
        query_predicates, candidate_predicates
    )
    elapsed = source.observed_at - source.candidate_last_seen_at
    time_score = 10.0 * max(0.0, 1.0 - elapsed / story_event_window(event_type))
    components = StoryCandidateScoreComponents(
        vector_score,
        primary_score,
        overlap_score,
        predicate_score,
        time_score,
    )
    return StoryCandidateScore(
        sum(
            (
                components.vector_similarity,
                components.primary_entity,
                components.entity_overlap,
                components.predicate_compatibility,
                components.time_distance,
            )
        ),
        components,
        (
            "VECTOR_SIMILARITY_SCORED",
            primary_reason,
            overlap_reason,
            predicate_reason,
            "TIME_DISTANCE_SCORED",
        ),
    )
