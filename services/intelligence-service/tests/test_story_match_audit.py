from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from footballpulse_intelligence_service.domain.story_candidate_decision import (
    CandidateDecisionInput,
    StoryCandidateDecisionPolicy,
    StoryCandidatePolicyConfig,
)
from footballpulse_intelligence_service.domain.story_candidate_scoring import (
    StoryCandidateScore,
    StoryCandidateScoreComponents,
)
from footballpulse_intelligence_service.domain.story_match_audit import StoryMatchAuditRecord

ARTICLE_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3cb003")
STORY_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3cb001")
NOW = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)


def test_audit_record_is_deterministic_and_captures_ranked_score_breakdown() -> None:
    score = StoryCandidateScore(
        total=81.5,
        components=StoryCandidateScoreComponents(24.0, 25.0, 7.5, 20.0, 5.0),
        reason_codes=("PRIMARY_ENTITY_MATCH", "PREDICATE_PROGRESSION"),
    )
    decision = StoryCandidateDecisionPolicy(
        StoryCandidatePolicyConfig(55.0, 75.0, 5.0, "story-matcher-v1")
    ).decide(
        candidates=(CandidateDecisionInput(STORY_ID, 3, score),),
        missing_current_embedding_story_ids=(),
        embedding_model_name="BAAI/bge-small-en-v1.5",
        embedding_model_version="pinned-revision",
    )

    first = StoryMatchAuditRecord.create(
        article_version_id=ARTICLE_ID,
        input_hash="a" * 64,
        decision=decision,
        now=NOW,
    )
    replay = StoryMatchAuditRecord.create(
        article_version_id=ARTICLE_ID,
        input_hash="a" * 64,
        decision=decision,
        now=NOW,
    )

    assert first == replay
    assert first.review_threshold == Decimal("55.000")
    assert first.candidates[0].rank == 1
    assert first.candidates[0].story_version == 3
    assert first.candidates[0].total_score == Decimal("81.500")
    assert first.candidates[0].components.predicate_compatibility == Decimal("20.000")
