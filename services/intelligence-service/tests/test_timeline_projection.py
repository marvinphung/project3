from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from footballpulse_intelligence_service.domain.claim_confirmation import ClaimConfirmation
from footballpulse_intelligence_service.domain.timeline import TimelineEntry
from footballpulse_intelligence_service.domain.timeline_projection import project_public_timeline

NOW = datetime(2026, 8, 1, 5, tzinfo=UTC)


def test_public_projection_contains_vietnamese_timeline_fields_only() -> None:
    entry = TimelineEntry.create(
        entry_id=UUID(int=1),
        story_id=UUID(int=2),
        window_start=NOW,
        summary_en="Arsenal submitted a bid.",
        summary_vi="Arsenal đã gửi đề nghị.",
        confirmation=ClaimConfirmation.REPORTED,
        used_claim_ids=(UUID(int=3),),
        source_article_ids=(UUID(int=4),),
        created_at=NOW,
    )

    result = project_public_timeline(entry)

    assert result.summary_vi == "Arsenal đã gửi đề nghị."
    assert result.story_id == entry.story_id
    assert not hasattr(result, "summary_en")
