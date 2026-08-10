from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from footballpulse_intelligence_service.domain.delivery import ProcessedEvent
from footballpulse_intelligence_service.domain.story_match_audit import StoryMatchAuditRecord
from footballpulse_intelligence_service.persistence.match_audit_repository import (
    PostgresStoryMatchAuditRepository,
    _candidate_values,
    _decision_values,
)
from footballpulse_intelligence_service.persistence.postgres_tables import (
    processed_events,
    story_match_candidate_scores,
    story_match_decisions,
)


class PostgresStoryMatchCommitRepository:
    """Persist audit and processed marker in one PostgreSQL transaction."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._audit_reader = PostgresStoryMatchAuditRepository(engine)

    def commit(
        self,
        record: StoryMatchAuditRecord,
        processed_event: ProcessedEvent,
    ) -> StoryMatchAuditRecord:
        PostgresStoryMatchAuditRepository._validate(record)
        decision_insert = (
            insert(story_match_decisions)
            .values(**_decision_values(record))
            .on_conflict_do_nothing(index_elements=[story_match_decisions.c.id])
            .returning(story_match_decisions.c.id)
        )
        marker_insert = (
            insert(processed_events)
            .values(
                id=processed_event.id,
                consumer_name=processed_event.consumer_name,
                event_id=processed_event.event_id,
                event_type=processed_event.event_type,
                processed_at=processed_event.processed_at,
            )
            .on_conflict_do_nothing(
                index_elements=[processed_events.c.consumer_name, processed_events.c.event_id]
            )
            .returning(processed_events.c.id)
        )
        with self._engine.begin() as connection:
            inserted = connection.execute(decision_insert).scalar_one_or_none()
            if inserted is not None and record.candidates:
                connection.execute(
                    story_match_candidate_scores.insert(),
                    [_candidate_values(candidate) for candidate in record.candidates],
                )
            connection.execute(marker_insert)
        persisted = self._audit_reader.get(record.id)
        if persisted is None:
            raise RuntimeError("committed Story match audit could not be read")
        return persisted
