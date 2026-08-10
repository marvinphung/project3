from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from footballpulse_intelligence_service.domain.delivery import ProcessedEvent
from footballpulse_intelligence_service.persistence.postgres_tables import processed_events


class PostgresProcessedEventStore:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def is_processed(self, consumer_name: str, event_id: UUID) -> bool:
        statement = sa.select(processed_events.c.id).where(
            processed_events.c.consumer_name == consumer_name,
            processed_events.c.event_id == event_id,
        )
        with self._engine.connect() as connection:
            return connection.execute(statement).scalar_one_or_none() is not None

    def mark_processed(self, event: ProcessedEvent) -> bool:
        statement = (
            insert(processed_events)
            .values(
                id=event.id,
                consumer_name=event.consumer_name,
                event_id=event.event_id,
                event_type=event.event_type,
                processed_at=event.processed_at,
            )
            .on_conflict_do_nothing(
                index_elements=[processed_events.c.consumer_name, processed_events.c.event_id]
            )
            .returning(processed_events.c.id)
        )
        with self._engine.begin() as connection:
            return connection.execute(statement).scalar_one_or_none() is not None
