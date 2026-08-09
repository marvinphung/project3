from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from footballpulse_crawler_service.application.source_service import SourceService
from footballpulse_crawler_service.domain.errors import SourceConflictError
from footballpulse_crawler_service.domain.source import NewSource, Source, SourceType

NOW = datetime(2026, 8, 1, tzinfo=UTC)
SOURCE_ID = UUID("00000000-0000-0000-0000-000000000101")


class InMemorySourceRepository:
    def __init__(self) -> None:
        self.sources: dict[UUID, Source] = {}

    def add(self, source: Source) -> Source:
        self.sources[source.id] = source
        return source

    def get(self, source_id: UUID) -> Source | None:
        return self.sources.get(source_id)

    def list_sources(self, *, limit: int, offset: int) -> list[Source]:
        return list(self.sources.values())[offset : offset + limit]

    def save(self, source: Source, *, expected_version: int) -> Source:
        current = self.sources[source.id]
        if current.version != expected_version:
            raise SourceConflictError("concurrent update")
        self.sources[source.id] = source
        return source

    def due(self, *, at: datetime, limit: int) -> list[Source]:
        return [source for source in self.sources.values() if source.is_due(at)][:limit]


def source_configuration() -> NewSource:
    return NewSource.create(
        name="BBC Sport",
        rss_url="https://www.bbc.com/sport/football/rss.xml",
        allowed_domains=["bbc.com"],
        source_type=SourceType.RSS,
        reliability_tier=1,
        crawl_interval_minutes=360,
        max_concurrency=2,
    )


def test_create_list_due_and_toggle_source() -> None:
    repository = InMemorySourceRepository()
    service = SourceService(repository, clock=lambda: NOW, id_factory=lambda: SOURCE_ID)

    created = service.create(source_configuration())
    assert service.list_sources() == [created]
    assert service.due(at=NOW) == [created]

    disabled = service.toggle(created.id, enabled=False, expected_version=1)
    assert disabled.enabled is False
    assert disabled.version == 2
    assert service.due(at=NOW) == []


def test_toggle_rejects_stale_expected_version() -> None:
    repository = InMemorySourceRepository()
    service = SourceService(repository, clock=lambda: NOW, id_factory=lambda: SOURCE_ID)
    created = service.create(source_configuration())

    with pytest.raises(SourceConflictError, match="version conflict"):
        service.toggle(created.id, enabled=False, expected_version=7)
