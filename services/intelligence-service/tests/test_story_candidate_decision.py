from __future__ import annotations

from uuid import UUID

import pytest
from footballpulse_intelligence_service.domain.story_candidate_decision import (
    CandidateDecisionInput,
    MatchAction,
    StoryCandidateDecisionPolicy,
    StoryCandidatePolicyConfig,
    StoryCandidateRetryableError,
)
from footballpulse_intelligence_service.domain.story_candidate_scoring import (
    StoryCandidateScore,
    StoryCandidateScoreComponents,
)

STORY_A = UUID("018f8b45-b634-7c81-a47d-9a7c2f3cb001")
STORY_B = UUID("018f8b45-b634-7c81-a47d-9a7c2f3cb002")
STORY_MISSING = UUID("018f8b45-b634-7c81-a47d-9a7c2f3cb003")
CONFIG = StoryCandidatePolicyConfig(
    review_threshold=55.0,
    attach_threshold=75.0,
    near_tie_margin=5.0,
    matcher_version="story-matcher-v1",
)


def candidate(
    story_id: UUID,
    total: float,
    *reasons: str,
) -> CandidateDecisionInput:
    remaining = total
    component_values: list[float] = []
    for maximum in (30.0, 25.0, 15.0, 20.0, 10.0):
        value = min(remaining, maximum)
        component_values.append(value)
        remaining -= value
    return CandidateDecisionInput(
        story_id=story_id,
        story_version=3,
        score=StoryCandidateScore(
            total=total,
            components=StoryCandidateScoreComponents(*component_values),
            reason_codes=reasons or ("PRIMARY_ENTITY_MATCH",),
        ),
    )


def test_policy_attaches_clear_high_scoring_candidate_with_audit_context() -> None:
    decision = StoryCandidateDecisionPolicy(CONFIG).decide(
        candidates=(candidate(STORY_B, 70), candidate(STORY_A, 80)),
        missing_current_embedding_story_ids=(),
        embedding_model_name="BAAI/bge-small-en-v1.5",
        embedding_model_version="pinned-revision",
    )

    assert decision.action is MatchAction.ATTACH
    assert decision.selected_story_id == STORY_A
    assert decision.selected_story_version == 3
    assert [item.story_id for item in decision.ranked_candidates] == [STORY_A, STORY_B]
    assert decision.reason_codes == ("TOP_SCORE_ATTACHABLE",)
    assert decision.matcher_version == "story-matcher-v1"
    assert decision.embedding_model_name == "BAAI/bge-small-en-v1.5"


@pytest.mark.parametrize(
    ("candidates", "expected_action", "expected_reason"),
    [
        ((), MatchAction.CREATE, "NO_CANDIDATES"),
        ((candidate(STORY_A, 40),), MatchAction.CREATE, "TOP_SCORE_BELOW_REVIEW_THRESHOLD"),
        ((candidate(STORY_A, 60),), MatchAction.REVIEW, "TOP_SCORE_IN_REVIEW_BAND"),
        (
            (candidate(STORY_A, 80), candidate(STORY_B, 76)),
            MatchAction.REVIEW,
            "CANDIDATE_NEAR_TIE",
        ),
        (
            (candidate(STORY_A, 90, "PRIMARY_ENTITY_CONFLICT"),),
            MatchAction.REVIEW,
            "PRIMARY_ENTITY_CONFLICT",
        ),
    ],
)
def test_policy_uses_safe_create_and_review_boundaries(
    candidates: tuple[CandidateDecisionInput, ...],
    expected_action: MatchAction,
    expected_reason: str,
) -> None:
    decision = StoryCandidateDecisionPolicy(CONFIG).decide(
        candidates=candidates,
        missing_current_embedding_story_ids=(),
        embedding_model_name="BAAI/bge-small-en-v1.5",
        embedding_model_version="pinned-revision",
    )

    assert decision.action is expected_action
    assert expected_reason in decision.reason_codes


def test_policy_retries_before_deciding_when_current_embedding_is_missing() -> None:
    with pytest.raises(StoryCandidateRetryableError) as captured:
        StoryCandidateDecisionPolicy(CONFIG).decide(
            candidates=(),
            missing_current_embedding_story_ids=(STORY_MISSING,),
            embedding_model_name="BAAI/bge-small-en-v1.5",
            embedding_model_version="pinned-revision",
        )

    assert captured.value.story_ids == (STORY_MISSING,)
