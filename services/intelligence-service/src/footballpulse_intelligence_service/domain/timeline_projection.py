from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from footballpulse_intelligence_service.domain.claim_confirmation import ClaimConfirmation
from footballpulse_intelligence_service.domain.timeline import TimelineEntry


@dataclass(frozen=True, slots=True)
class PublicTimelineItem:
    story_id: UUID
    window_start: datetime
    window_end: datetime
    summary_vi: str
    confirmation: ClaimConfirmation
    used_claim_ids: tuple[UUID, ...]
    source_article_ids: tuple[UUID, ...]


def project_public_timeline(entry: TimelineEntry) -> PublicTimelineItem:
    return PublicTimelineItem(
        story_id=entry.story_id,
        window_start=entry.window_start,
        window_end=entry.window_end,
        summary_vi=entry.summary_vi,
        confirmation=entry.confirmation,
        used_claim_ids=entry.used_claim_ids,
        source_article_ids=entry.source_article_ids,
    )
