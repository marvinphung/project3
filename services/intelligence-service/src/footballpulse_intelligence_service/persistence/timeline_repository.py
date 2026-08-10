from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine, RowMapping

from footballpulse_intelligence_service.domain.claim_confirmation import ClaimConfirmation
from footballpulse_intelligence_service.domain.timeline import TimelineEntry
from footballpulse_intelligence_service.persistence.postgres_tables import timeline_entries


def _values(entry: TimelineEntry) -> dict[str, object]:
    return {
        "id": entry.id,
        "story_id": entry.story_id,
        "window_start": entry.window_start,
        "window_end": entry.window_end,
        "summary_en": entry.summary_en,
        "summary_vi": entry.summary_vi,
        "confirmation": entry.confirmation.value,
        "used_claim_ids": [str(value) for value in entry.used_claim_ids],
        "source_article_ids": [str(value) for value in entry.source_article_ids],
        "created_at": entry.created_at,
    }


def _from_row(row: RowMapping) -> TimelineEntry:
    return TimelineEntry(
        id=row["id"],
        story_id=row["story_id"],
        window_start=row["window_start"],
        window_end=row["window_end"],
        summary_en=row["summary_en"],
        summary_vi=row["summary_vi"],
        confirmation=ClaimConfirmation(row["confirmation"]),
        used_claim_ids=tuple(UUID(value) for value in row["used_claim_ids"]),
        source_article_ids=tuple(UUID(value) for value in row["source_article_ids"]),
        created_at=row["created_at"],
    )


class PostgresTimelineRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def add_once(self, entry: TimelineEntry) -> bool:
        statement = (
            insert(timeline_entries)
            .values(**_values(entry))
            .on_conflict_do_nothing(
                index_elements=[timeline_entries.c.story_id, timeline_entries.c.window_start]
            )
            .returning(timeline_entries.c.id)
        )
        with self._engine.begin() as connection:
            return connection.execute(statement).scalar_one_or_none() is not None

    def get(self, story_id: UUID, window_start: datetime) -> TimelineEntry | None:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    sa.select(timeline_entries).where(
                        timeline_entries.c.story_id == story_id,
                        timeline_entries.c.window_start == window_start,
                    )
                )
                .mappings()
                .one_or_none()
            )
        return None if row is None else _from_row(row)
