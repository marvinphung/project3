from __future__ import annotations

from collections import defaultdict
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.engine import Engine

from footballpulse_intelligence_service.domain.entity import EntityType
from footballpulse_intelligence_service.domain.story import ClaimPredicate, StoryEventType
from footballpulse_intelligence_service.domain.story_matching_context import StoryCandidateContext
from footballpulse_intelligence_service.persistence.postgres_tables import (
    claims,
    stories,
    story_entities,
)

_PRIMARY_ENTITY_TYPES = {
    StoryEventType.TRANSFER: frozenset({EntityType.PLAYER.value}),
    StoryEventType.CONTRACT: frozenset({EntityType.PLAYER.value}),
    StoryEventType.INJURY: frozenset({EntityType.PLAYER.value}),
    StoryEventType.MANAGERIAL: frozenset({EntityType.COACH.value}),
    StoryEventType.MATCH: frozenset({EntityType.CLUB.value}),
    StoryEventType.DISCIPLINARY: frozenset({EntityType.PLAYER.value, EntityType.COACH.value}),
    StoryEventType.OTHER: frozenset(),
}


class PostgresStoryCandidateContextRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def load_current(self, story_ids: tuple[UUID, ...]) -> tuple[StoryCandidateContext, ...]:
        if not story_ids:
            return ()
        with self._engine.connect() as connection:
            story_rows = (
                connection.execute(
                    sa.select(stories.c.id, stories.c.version, stories.c.event_type).where(
                        stories.c.id.in_(story_ids)
                    )
                )
                .mappings()
                .all()
            )
            entity_rows = (
                connection.execute(
                    sa.select(
                        story_entities.c.story_id,
                        story_entities.c.entity_id,
                        story_entities.c.entity_type,
                    )
                    .where(story_entities.c.story_id.in_(story_ids))
                    .order_by(
                        story_entities.c.story_id,
                        story_entities.c.created_at,
                        story_entities.c.id,
                    )
                )
                .mappings()
                .all()
            )
            claim_rows = (
                connection.execute(
                    sa.select(claims.c.story_id, claims.c.predicate)
                    .where(claims.c.story_id.in_(story_ids))
                    .order_by(claims.c.story_id, claims.c.created_at, claims.c.id)
                )
                .mappings()
                .all()
            )
        entities_by_story: dict[UUID, list[tuple[UUID, str]]] = defaultdict(list)
        for row in entity_rows:
            entities_by_story[row["story_id"]].append((row["entity_id"], row["entity_type"]))
        predicates_by_story: dict[UUID, list[ClaimPredicate]] = defaultdict(list)
        for row in claim_rows:
            predicate = ClaimPredicate(row["predicate"])
            if predicate not in predicates_by_story[row["story_id"]]:
                predicates_by_story[row["story_id"]].append(predicate)

        by_id = {row["id"]: row for row in story_rows}
        contexts: list[StoryCandidateContext] = []
        for story_id in story_ids:
            story_row = by_id.get(story_id)
            if story_row is None:
                continue
            event_type = StoryEventType(story_row["event_type"])
            entities = entities_by_story[story_id]
            primary_types = _PRIMARY_ENTITY_TYPES[event_type]
            contexts.append(
                StoryCandidateContext(
                    story_id=story_id,
                    story_version=story_row["version"],
                    primary_entity_ids=tuple(
                        entity_id
                        for entity_id, entity_type in entities
                        if entity_type in primary_types
                    ),
                    entity_ids=tuple(entity_id for entity_id, _ in entities),
                    predicates=tuple(predicates_by_story[story_id]),
                )
            )
        return tuple(contexts)
