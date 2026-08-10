from __future__ import annotations

from typing import Protocol

from footballpulse_intelligence_service.domain.material_change import MaterialChangeResult
from footballpulse_intelligence_service.domain.timeline import TimelineEntry


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
            return False
        return self._repository.add_once(entry)
