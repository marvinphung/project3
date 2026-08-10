from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import Table
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection, Engine, RowMapping
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql.dml import ReturningInsert

from footballpulse_intelligence_service.domain.delivery import OutboxEvent, ProcessedEvent
from footballpulse_intelligence_service.domain.errors import StoryConflictError
from footballpulse_intelligence_service.domain.story import (
    Claim,
    ClaimEvidence,
    Story,
    StoryEntity,
    StoryEventType,
    StorySource,
    StoryStatus,
)
from footballpulse_intelligence_service.persistence.postgres_tables import (
    claim_evidence,
    processed_events,
    stories,
    story_entities,
    story_sources,
)
from footballpulse_intelligence_service.persistence.postgres_tables import (
    claims as claims_table,
)
from footballpulse_intelligence_service.persistence.postgres_tables import (
    outbox_events as outbox_events_table,
)


def _story_values(story: Story) -> dict[str, object]:
    return {
        "id": story.id,
        "event_type": story.event_type.value,
        "status": story.status.value,
        "confidence_score": story.confidence_score,
        "first_seen_at": story.first_seen_at,
        "last_seen_at": story.last_seen_at,
        "version": story.version,
        "created_at": story.created_at,
        "updated_at": story.updated_at,
    }


def _story_from_row(row: RowMapping) -> Story:
    return Story(
        id=row["id"],
        event_type=StoryEventType(row["event_type"]),
        status=StoryStatus(row["status"]),
        confidence_score=row["confidence_score"],
        first_seen_at=row["first_seen_at"],
        last_seen_at=row["last_seen_at"],
        version=row["version"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _source_values(source: StorySource) -> dict[str, object]:
    return {
        "id": source.id,
        "story_id": source.story_id,
        "article_version_id": source.article_version_id,
        "source_id": source.source_id,
        "source_cluster_id": source.source_cluster_id,
        "source_reliability_tier": source.source_reliability_tier,
        "published_at": source.published_at,
        "observed_at": source.observed_at,
    }


def _entity_values(entity: StoryEntity) -> dict[str, object]:
    return {
        "id": entity.id,
        "story_id": entity.story_id,
        "entity_id": entity.entity_id,
        "entity_type": entity.entity_type.value,
        "created_at": entity.created_at,
    }


def _claim_values(claim: Claim) -> dict[str, object]:
    return {
        "id": claim.id,
        "story_id": claim.story_id,
        "claim_fingerprint": claim.fingerprint,
        "subject_entity_id": claim.subject_entity_id,
        "predicate": claim.predicate.value,
        "object_entity_id": claim.object_entity_id,
        "object_value": claim.object_value,
        "statement_en": claim.statement_en,
        "certainty": claim.certainty,
        "occurred_at": claim.occurred_at,
        "occurred_at_bucket": claim.occurred_at_bucket,
        "created_at": claim.created_at,
        "confirmation": claim.confirmation.value,
    }


def _evidence_values(evidence: ClaimEvidence) -> dict[str, object]:
    return {
        "id": evidence.id,
        "claim_id": evidence.claim_id,
        "story_source_id": evidence.story_source_id,
        "evidence_quote": evidence.quote,
        "evidence_start": evidence.start,
        "evidence_end": evidence.end,
        "created_at": evidence.created_at,
    }


def _processed_values(event: ProcessedEvent) -> dict[str, object]:
    return {
        "id": event.id,
        "consumer_name": event.consumer_name,
        "event_id": event.event_id,
        "event_type": event.event_type,
        "processed_at": event.processed_at,
    }


def _outbox_values(event: OutboxEvent) -> dict[str, object]:
    return {
        "id": event.id,
        "aggregate_type": event.aggregate_type,
        "aggregate_id": event.aggregate_id,
        "event_type": event.event_type,
        "deduplication_key": event.deduplication_key,
        "payload": event.payload,
        "status": event.status.value,
        "attempt_count": event.attempt_count,
        "available_at": event.available_at,
        "published_at": event.published_at,
        "last_error": event.last_error,
        "created_at": event.created_at,
    }


class PostgresStoryRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def create_from_event(
        self,
        *,
        story: Story,
        sources: tuple[StorySource, ...],
        entities: tuple[StoryEntity, ...],
        claims: tuple[Claim, ...],
        evidence: tuple[ClaimEvidence, ...],
        processed_event: ProcessedEvent,
        outbox_events: tuple[OutboxEvent, ...],
    ) -> bool:
        self._validate_aggregate(story, sources, entities, claims, evidence, outbox_events)
        marker = (
            insert(processed_events)
            .values(**_processed_values(processed_event))
            .on_conflict_do_nothing(
                index_elements=[processed_events.c.consumer_name, processed_events.c.event_id]
            )
            .returning(processed_events.c.id)
        )
        try:
            with self._engine.begin() as connection:
                if connection.execute(marker).scalar_one_or_none() is None:
                    return False
                connection.execute(stories.insert().values(**_story_values(story)))
                self._insert_many(connection, story_sources, map(_source_values, sources))
                self._insert_many(connection, story_entities, map(_entity_values, entities))
                self._insert_many(connection, claims_table, map(_claim_values, claims))
                self._insert_many(
                    connection,
                    claim_evidence,
                    map(_evidence_values, evidence),
                )
                self._insert_many(
                    connection,
                    outbox_events_table,
                    map(_outbox_values, outbox_events),
                )
        except IntegrityError as error:
            raise StoryConflictError("Story aggregate conflicts with persisted data") from error
        return True

    def get(self, story_id: UUID) -> Story | None:
        with self._engine.connect() as connection:
            row = (
                connection.execute(sa.select(stories).where(stories.c.id == story_id))
                .mappings()
                .one_or_none()
            )
        return None if row is None else _story_from_row(row)

    def update_from_event(
        self,
        *,
        story: Story,
        expected_version: int,
        sources: tuple[StorySource, ...],
        entities: tuple[StoryEntity, ...],
        claims: tuple[Claim, ...],
        evidence: tuple[ClaimEvidence, ...],
        processed_event: ProcessedEvent,
        outbox_events: tuple[OutboxEvent, ...],
    ) -> bool:
        if expected_version < 1 or story.version != expected_version + 1:
            raise ValueError("updated Story version must follow expected_version")
        self._validate_members(story, sources, entities, claims, outbox_events)
        marker = self._processed_marker(processed_event)
        values = _story_values(story)
        for immutable in ("id", "event_type", "first_seen_at", "created_at"):
            values.pop(immutable)
        try:
            with self._engine.begin() as connection:
                if connection.execute(marker).scalar_one_or_none() is None:
                    return False
                updated = connection.execute(
                    stories.update()
                    .where(stories.c.id == story.id, stories.c.version == expected_version)
                    .values(**values)
                    .returning(stories.c.id)
                ).scalar_one_or_none()
                if updated is None:
                    raise StoryConflictError("Story version changed before update")
                self._validate_evidence_ownership(
                    connection,
                    story.id,
                    claims,
                    sources,
                    evidence,
                )
                self._insert_many(connection, story_sources, map(_source_values, sources))
                self._insert_many(connection, story_entities, map(_entity_values, entities))
                self._insert_many(connection, claims_table, map(_claim_values, claims))
                self._insert_many(connection, claim_evidence, map(_evidence_values, evidence))
                self._insert_many(
                    connection,
                    outbox_events_table,
                    map(_outbox_values, outbox_events),
                )
        except IntegrityError as error:
            raise StoryConflictError("Story update conflicts with persisted data") from error
        return True

    @staticmethod
    def _processed_marker(event: ProcessedEvent) -> ReturningInsert[Any]:
        return (
            insert(processed_events)
            .values(**_processed_values(event))
            .on_conflict_do_nothing(
                index_elements=[processed_events.c.consumer_name, processed_events.c.event_id]
            )
            .returning(processed_events.c.id)
        )

    @staticmethod
    def _insert_many(
        connection: Connection,
        table: Table,
        rows: Iterable[dict[str, object]],
    ) -> None:
        values = list(rows)
        if values:
            connection.execute(table.insert(), values)

    @staticmethod
    def _validate_aggregate(
        story: Story,
        sources: tuple[StorySource, ...],
        entities: tuple[StoryEntity, ...],
        claim_records: tuple[Claim, ...],
        evidence: tuple[ClaimEvidence, ...],
        events: tuple[OutboxEvent, ...],
    ) -> None:
        if not sources:
            raise ValueError("new Story aggregate requires at least one source")
        if not claim_records:
            raise ValueError("new Story aggregate requires at least one claim")
        if not evidence:
            raise ValueError("new Story aggregate requires claim evidence")
        if not events:
            raise ValueError("new Story aggregate requires an outbox event")
        PostgresStoryRepository._validate_members(
            story,
            sources,
            entities,
            claim_records,
            events,
        )
        claim_ids = {claim.id for claim in claim_records}
        source_ids = {source.id for source in sources}
        entity_ids = {entity.entity_id for entity in entities}
        required_entity_ids = {claim.subject_entity_id for claim in claim_records}
        required_entity_ids.update(
            claim.object_entity_id
            for claim in claim_records
            if claim.object_entity_id is not None
        )
        if not required_entity_ids <= entity_ids:
            raise ValueError("every claim entity must be linked to the Story aggregate")
        if any(
            item.claim_id not in claim_ids or item.story_source_id not in source_ids
            for item in evidence
        ):
            raise ValueError("claim evidence points outside the Story aggregate")

    @staticmethod
    def _validate_members(
        story: Story,
        sources: tuple[StorySource, ...],
        entities: tuple[StoryEntity, ...],
        claim_records: tuple[Claim, ...],
        events: tuple[OutboxEvent, ...],
    ) -> None:
        if any(source.story_id != story.id for source in sources):
            raise ValueError("aggregate member belongs to a different Story")
        if any(entity.story_id != story.id for entity in entities):
            raise ValueError("aggregate member belongs to a different Story")
        if any(claim.story_id != story.id for claim in claim_records):
            raise ValueError("aggregate member belongs to a different Story")
        if any(event.aggregate_id != story.id for event in events):
            raise ValueError("outbox event belongs to a different aggregate")
        if any(event.aggregate_type != "STORY" for event in events):
            raise ValueError("outbox event must use the STORY aggregate type")

    @staticmethod
    def _validate_evidence_ownership(
        connection: Connection,
        story_id: UUID,
        new_claims: tuple[Claim, ...],
        new_sources: tuple[StorySource, ...],
        evidence: tuple[ClaimEvidence, ...],
    ) -> None:
        claim_ids = {claim.id for claim in new_claims}
        source_ids = {source.id for source in new_sources}
        required_claim_ids = {item.claim_id for item in evidence} - claim_ids
        required_source_ids = {item.story_source_id for item in evidence} - source_ids
        if required_claim_ids:
            owned_claim_ids = set(
                connection.execute(
                    sa.select(claims_table.c.id).where(
                        claims_table.c.story_id == story_id,
                        claims_table.c.id.in_(required_claim_ids),
                    )
                ).scalars()
            )
            if owned_claim_ids != required_claim_ids:
                raise ValueError("claim evidence points outside the Story aggregate")
        if required_source_ids:
            owned_source_ids = set(
                connection.execute(
                    sa.select(story_sources.c.id).where(
                        story_sources.c.story_id == story_id,
                        story_sources.c.id.in_(required_source_ids),
                    )
                ).scalars()
            )
            if owned_source_ids != required_source_ids:
                raise ValueError("claim evidence points outside the Story aggregate")
