from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from footballpulse_intelligence_service.domain.claim_confirmation import ClaimConfirmation

VIETNAM_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def _aware(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value


def _text(value: str, field: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError(f"{field} must not be empty")
    return normalized


def timeline_window_start(value: datetime) -> datetime:
    observed_at = _aware(value, "window timestamp")
    local = observed_at.astimezone(VIETNAM_TZ)
    local_start = local.replace(hour=(local.hour // 6) * 6, minute=0, second=0, microsecond=0)
    return local_start.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class TimelineEntry:
    id: UUID
    story_id: UUID
    window_start: datetime
    window_end: datetime
    summary_en: str
    summary_vi: str
    confirmation: ClaimConfirmation
    used_claim_ids: tuple[UUID, ...]
    source_article_ids: tuple[UUID, ...]
    created_at: datetime

    @classmethod
    def create(
        cls,
        *,
        entry_id: UUID,
        story_id: UUID,
        window_start: datetime,
        summary_en: str,
        summary_vi: str,
        confirmation: ClaimConfirmation,
        used_claim_ids: tuple[UUID, ...],
        source_article_ids: tuple[UUID, ...],
        created_at: datetime,
    ) -> TimelineEntry:
        start = _aware(window_start, "window_start")
        if timeline_window_start(start) != start.astimezone(UTC):
            raise ValueError("window_start must align to a Vietnam six-hour boundary")
        if not used_claim_ids:
            raise ValueError("timeline entry requires at least one claim")
        if not source_article_ids:
            raise ValueError("timeline entry requires at least one source article")
        return cls(
            entry_id,
            story_id,
            start.astimezone(UTC),
            start.astimezone(UTC) + timedelta(hours=6),
            _text(summary_en, "summary_en"),
            _text(summary_vi, "summary_vi"),
            ClaimConfirmation(confirmation),
            tuple(dict.fromkeys(used_claim_ids)),
            tuple(dict.fromkeys(source_article_ids)),
            _aware(created_at, "created_at"),
        )
