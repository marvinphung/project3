from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from footballpulse_intelligence_service.domain.claim_confirmation import ClaimConfirmation
from footballpulse_intelligence_service.domain.timeline import (
    TimelineEntry,
    timeline_window_start,
)

STORY_ID = UUID(int=1)
CLAIM_ID = UUID(int=2)
SOURCE_ID = UUID(int=3)


def test_window_uses_vietnam_local_six_hour_boundaries() -> None:
    assert timeline_window_start(datetime(2026, 8, 1, 5, 59, tzinfo=UTC)) == datetime(
        2026, 8, 1, 5, 0, tzinfo=UTC
    )
    assert timeline_window_start(datetime(2026, 8, 1, 6, 0, tzinfo=UTC)) == datetime(
        2026, 8, 1, 5, 0, tzinfo=UTC
    )


def test_timeline_entry_has_exact_six_hour_window_and_bilingual_text() -> None:
    start = datetime(2026, 8, 1, 5, 0, tzinfo=UTC)
    entry = TimelineEntry.create(
        entry_id=UUID(int=10),
        story_id=STORY_ID,
        window_start=start,
        summary_en="Arsenal submitted a bid.",
        summary_vi="Arsenal đã gửi đề nghị.",
        confirmation=ClaimConfirmation.REPORTED,
        used_claim_ids=(CLAIM_ID,),
        source_article_ids=(SOURCE_ID,),
        created_at=start,
    )

    assert entry.window_end == start + timedelta(hours=6)
    assert entry.summary_en == "Arsenal submitted a bid."
    assert entry.summary_vi == "Arsenal đã gửi đề nghị."


def test_timeline_entry_rejects_empty_grounding_or_naive_time() -> None:
    with pytest.raises(ValueError, match="claim"):
        TimelineEntry.create(
            entry_id=UUID(int=10),
            story_id=STORY_ID,
            window_start=datetime(2026, 8, 1, 5, tzinfo=UTC),
            summary_en="A claim.",
            summary_vi="Một claim.",
            confirmation=ClaimConfirmation.REPORTED,
            used_claim_ids=(),
            source_article_ids=(SOURCE_ID,),
            created_at=datetime(2026, 8, 1, 5, tzinfo=UTC),
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        timeline_window_start(datetime(2026, 8, 1, 5))
