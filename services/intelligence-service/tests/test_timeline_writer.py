from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from footballpulse_intelligence_service.application.timeline_writer import TimelineWriter
from footballpulse_intelligence_service.domain.claim_confirmation import ClaimConfirmation
from footballpulse_intelligence_service.domain.material_change import MaterialChangeResult
from footballpulse_intelligence_service.domain.timeline import TimelineEntry

NOW = datetime(2026, 8, 1, 5, tzinfo=UTC)


class FakeTimelineRepository:
    def __init__(self) -> None:
        self.entries: list[TimelineEntry] = []

    def add_once(self, entry: TimelineEntry) -> bool:
        if any(
            item.story_id == entry.story_id and item.window_start == entry.window_start
            for item in self.entries
        ):
            return False
        self.entries.append(entry)
        return True


def entry() -> TimelineEntry:
    return TimelineEntry.create(
        entry_id=UUID(int=10),
        story_id=UUID(int=1),
        window_start=NOW,
        summary_en="Arsenal submitted a bid.",
        summary_vi="Arsenal đã gửi đề nghị.",
        confirmation=ClaimConfirmation.REPORTED,
        used_claim_ids=(UUID(int=2),),
        source_article_ids=(UUID(int=3),),
        created_at=NOW,
    )


def test_writer_skips_window_without_material_change() -> None:
    repository = FakeTimelineRepository()
    writer = TimelineWriter(repository)

    written = writer.write_if_material(
        MaterialChangeResult(False, ()),
        entry(),
    )

    assert written is False
    assert repository.entries == []


def test_writer_persists_material_change_and_replay_is_noop() -> None:
    repository = FakeTimelineRepository()
    writer = TimelineWriter(repository)
    material = MaterialChangeResult(True, ("NEW_CLAIM",))

    assert writer.write_if_material(material, entry()) is True
    assert writer.write_if_material(material, entry()) is False
    assert len(repository.entries) == 1
