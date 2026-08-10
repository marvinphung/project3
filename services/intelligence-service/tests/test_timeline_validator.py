from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from footballpulse_intelligence_service.domain.claim_confirmation import ClaimConfirmation
from footballpulse_intelligence_service.domain.timeline import TimelineEntry
from footballpulse_intelligence_service.domain.timeline_validator import (
    TimelineValidationCode,
    TimelineValidator,
)

NOW = datetime(2026, 8, 1, 5, tzinfo=UTC)
CLAIM_ID = UUID(int=1)
SOURCE_ID = UUID(int=2)


def entry(
    *,
    claims: tuple[UUID, ...] = (CLAIM_ID,),
    sources: tuple[UUID, ...] = (SOURCE_ID,),
) -> TimelineEntry:
    return TimelineEntry.create(
        entry_id=UUID(int=3),
        story_id=UUID(int=4),
        window_start=NOW,
        summary_en="Arsenal submitted a bid.",
        summary_vi="Arsenal đã gửi đề nghị.",
        confirmation=ClaimConfirmation.REPORTED,
        used_claim_ids=claims,
        source_article_ids=sources,
        created_at=NOW,
    )


def test_validator_accepts_matching_grounding() -> None:
    result = TimelineValidator().validate(
        entry(), expected_claim_ids=(CLAIM_ID,), expected_source_article_ids=(SOURCE_ID,)
    )

    assert result.is_valid is True
    assert result.codes == ()


def test_validator_rejects_missing_or_extra_grounding() -> None:
    result = TimelineValidator().validate(
        entry(claims=(CLAIM_ID, UUID(int=5))),
        expected_claim_ids=(CLAIM_ID,),
        expected_source_article_ids=(SOURCE_ID,),
    )

    assert result.is_valid is False
    assert result.codes == (TimelineValidationCode.CLAIM_SET_MISMATCH,)
