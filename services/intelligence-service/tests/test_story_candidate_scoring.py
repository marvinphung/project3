from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from footballpulse_intelligence_service.domain.story import (
    ClaimPredicate,
    StoryEventType,
)
from footballpulse_intelligence_service.domain.story_candidate_scoring import (
    StoryCandidateScoreInput,
    score_story_candidate,
)

PLAYER_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c8101")
REAL_MADRID_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c8102")
ARSENAL_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c8103")
CHELSEA_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c8104")
OTHER_PLAYER_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c8105")
NOW = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)


def test_score_breakdown_rewards_transfer_progression_and_shared_context() -> None:
    result = score_story_candidate(
        StoryCandidateScoreInput(
            event_type=StoryEventType.TRANSFER,
            cosine_similarity=0.8,
            query_primary_entity_ids=(PLAYER_ID,),
            candidate_primary_entity_ids=(PLAYER_ID,),
            query_entity_ids=(PLAYER_ID, REAL_MADRID_ID, ARSENAL_ID),
            candidate_entity_ids=(PLAYER_ID, REAL_MADRID_ID, CHELSEA_ID),
            query_predicates=(ClaimPredicate.SUBMITTED_BID,),
            candidate_predicates=(ClaimPredicate.CONTACTED,),
            observed_at=NOW,
            candidate_last_seen_at=NOW - timedelta(days=15),
        )
    )

    assert result.total == pytest.approx(81.5)
    assert result.components.vector_similarity == pytest.approx(24.0)
    assert result.components.primary_entity == pytest.approx(25.0)
    assert result.components.entity_overlap == pytest.approx(7.5)
    assert result.components.predicate_compatibility == pytest.approx(20.0)
    assert result.components.time_distance == pytest.approx(5.0)
    assert result.reason_codes == (
        "VECTOR_SIMILARITY_SCORED",
        "PRIMARY_ENTITY_MATCH",
        "SECONDARY_ENTITY_PARTIAL_OVERLAP",
        "PREDICATE_PROGRESSION",
        "TIME_DISTANCE_SCORED",
    )


@pytest.mark.parametrize(
    ("query_primary", "candidate_primary", "reason"),
    [
        ((), (PLAYER_ID,), "QUERY_PRIMARY_ENTITY_MISSING"),
        ((PLAYER_ID,), (), "CANDIDATE_PRIMARY_ENTITY_MISSING"),
        ((PLAYER_ID,), (OTHER_PLAYER_ID,), "PRIMARY_ENTITY_CONFLICT"),
    ],
)
def test_score_exposes_primary_identity_safety_reasons(
    query_primary: tuple[UUID, ...],
    candidate_primary: tuple[UUID, ...],
    reason: str,
) -> None:
    result = score_story_candidate(
        StoryCandidateScoreInput(
            event_type=StoryEventType.TRANSFER,
            cosine_similarity=1.0,
            query_primary_entity_ids=query_primary,
            candidate_primary_entity_ids=candidate_primary,
            query_entity_ids=(PLAYER_ID, REAL_MADRID_ID),
            candidate_entity_ids=(PLAYER_ID, REAL_MADRID_ID),
            query_predicates=(ClaimPredicate.SUBMITTED_BID,),
            candidate_predicates=(ClaimPredicate.SUBMITTED_BID,),
            observed_at=NOW,
            candidate_last_seen_at=NOW,
        )
    )

    assert result.components.primary_entity == 0
    assert reason in result.reason_codes


def test_score_rejects_observation_before_candidate_last_seen() -> None:
    with pytest.raises(ValueError, match="cannot be before candidate_last_seen_at"):
        score_story_candidate(
            StoryCandidateScoreInput(
                event_type=StoryEventType.TRANSFER,
                cosine_similarity=0.9,
                query_primary_entity_ids=(PLAYER_ID,),
                candidate_primary_entity_ids=(PLAYER_ID,),
                query_entity_ids=(PLAYER_ID,),
                candidate_entity_ids=(PLAYER_ID,),
                query_predicates=(ClaimPredicate.CONTACTED,),
                candidate_predicates=(ClaimPredicate.CONTACTED,),
                observed_at=NOW - timedelta(seconds=1),
                candidate_last_seen_at=NOW,
            )
        )
