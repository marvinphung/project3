from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection, Engine, RowMapping

from footballpulse_intelligence_service.domain.story_candidate_decision import MatchAction
from footballpulse_intelligence_service.domain.story_match_audit import (
    StoryMatchAuditCandidate,
    StoryMatchAuditRecord,
    StoryMatchAuditScoreComponents,
)
from footballpulse_intelligence_service.persistence.postgres_tables import (
    story_match_candidate_scores,
    story_match_decisions,
)


def _decision_values(record: StoryMatchAuditRecord) -> dict[str, object]:
    return {
        "id": record.id,
        "article_version_id": record.article_version_id,
        "input_hash": record.input_hash,
        "candidate_set_hash": record.candidate_set_hash,
        "action": record.action.value,
        "selected_story_id": record.selected_story_id,
        "selected_story_version": record.selected_story_version,
        "review_threshold": record.review_threshold,
        "attach_threshold": record.attach_threshold,
        "near_tie_margin": record.near_tie_margin,
        "matcher_version": record.matcher_version,
        "embedding_model_name": record.embedding_model_name,
        "embedding_model_version": record.embedding_model_version,
        "reason_codes": list(record.reason_codes),
        "created_at": record.created_at,
    }


def _candidate_values(candidate: StoryMatchAuditCandidate) -> dict[str, object]:
    return {
        "id": candidate.id,
        "decision_id": candidate.decision_id,
        "rank": candidate.rank,
        "story_id": candidate.story_id,
        "story_version": candidate.story_version,
        "total_score": candidate.total_score,
        "vector_similarity_score": candidate.components.vector_similarity,
        "primary_entity_score": candidate.components.primary_entity,
        "entity_overlap_score": candidate.components.entity_overlap,
        "predicate_compatibility_score": candidate.components.predicate_compatibility,
        "time_distance_score": candidate.components.time_distance,
        "reason_codes": list(candidate.reason_codes),
    }


def _candidate_from_row(row: RowMapping) -> StoryMatchAuditCandidate:
    return StoryMatchAuditCandidate(
        row["id"],
        row["decision_id"],
        row["rank"],
        row["story_id"],
        row["story_version"],
        row["total_score"],
        StoryMatchAuditScoreComponents(
            row["vector_similarity_score"],
            row["primary_entity_score"],
            row["entity_overlap_score"],
            row["predicate_compatibility_score"],
            row["time_distance_score"],
        ),
        tuple(row["reason_codes"]),
    )


class PostgresStoryMatchAuditRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def add_once(self, record: StoryMatchAuditRecord) -> StoryMatchAuditRecord:
        self._validate(record)
        statement = (
            insert(story_match_decisions)
            .values(**_decision_values(record))
            .on_conflict_do_nothing(index_elements=[story_match_decisions.c.id])
            .returning(story_match_decisions.c.id)
        )
        with self._engine.begin() as connection:
            inserted = connection.execute(statement).scalar_one_or_none()
            if inserted is None:
                persisted = self._get(connection, record.id)
                if persisted is None:
                    raise RuntimeError("Story match audit conflict did not resolve to a record")
                return persisted
            if record.candidates:
                connection.execute(
                    story_match_candidate_scores.insert(),
                    [_candidate_values(candidate) for candidate in record.candidates],
                )
        return record

    def get(self, decision_id: UUID) -> StoryMatchAuditRecord | None:
        with self._engine.connect() as connection:
            return self._get(connection, decision_id)

    @staticmethod
    def _get(connection: Connection, decision_id: UUID) -> StoryMatchAuditRecord | None:
        decision = (
            connection.execute(
                sa.select(story_match_decisions).where(story_match_decisions.c.id == decision_id)
            )
            .mappings()
            .one_or_none()
        )
        if decision is None:
            return None
        candidate_rows = (
            connection.execute(
                sa.select(story_match_candidate_scores)
                .where(story_match_candidate_scores.c.decision_id == decision_id)
                .order_by(story_match_candidate_scores.c.rank)
            )
            .mappings()
            .all()
        )
        return StoryMatchAuditRecord(
            decision["id"],
            decision["article_version_id"],
            decision["input_hash"],
            decision["candidate_set_hash"],
            MatchAction(decision["action"]),
            decision["selected_story_id"],
            decision["selected_story_version"],
            decision["review_threshold"],
            decision["attach_threshold"],
            decision["near_tie_margin"],
            decision["matcher_version"],
            decision["embedding_model_name"],
            decision["embedding_model_version"],
            tuple(decision["reason_codes"]),
            tuple(_candidate_from_row(row) for row in candidate_rows),
            decision["created_at"],
        )

    @staticmethod
    def _validate(record: StoryMatchAuditRecord) -> None:
        ranks = tuple(candidate.rank for candidate in record.candidates)
        if ranks != tuple(range(1, len(record.candidates) + 1)):
            raise ValueError("audit candidate ranks must be contiguous and ordered")
        if any(candidate.decision_id != record.id for candidate in record.candidates):
            raise ValueError("audit candidates must belong to the decision")
        if record.action is MatchAction.CREATE:
            if record.selected_story_id is not None or record.selected_story_version is not None:
                raise ValueError("CREATE audit cannot select a Story")
        elif not any(
            candidate.story_id == record.selected_story_id
            and candidate.story_version == record.selected_story_version
            for candidate in record.candidates
        ):
            raise ValueError("selected Story must be present at the audited version")
