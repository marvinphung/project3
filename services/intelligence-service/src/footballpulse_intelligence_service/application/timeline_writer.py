from __future__ import annotations

import logging
from typing import Protocol

from footballpulse_runtime_config import log_event

from footballpulse_intelligence_service.domain.material_change import MaterialChangeResult
from footballpulse_intelligence_service.domain.timeline import TimelineEntry

LOGGER = logging.getLogger("footballpulse.intelligence.timeline")


class TimelineRepository(Protocol):
    def add_once(self, entry: TimelineEntry) -> bool: ...


class TimelineWriter:
    def __init__(self, repository: TimelineRepository) -> None:
        self._repository = repository

    def write_if_material(
        self,
        change: MaterialChangeResult,
        entry: TimelineEntry,
    ) -> bool:
        if not change.changed:
            log_event(
                LOGGER,
                "timeline_unchanged",
                story_id=str(entry.story_id),
                timeline_entry_id=str(entry.id),
            )
            return False
        created = self._repository.add_once(entry)
        log_event(
            LOGGER,
            "timeline_entry_created" if created else "timeline_entry_duplicate",
            story_id=str(entry.story_id),
            timeline_entry_id=str(entry.id),
        )
        return created
