from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine, RowMapping
from sqlalchemy.sql.elements import ColumnElement

from footballpulse_intelligence_service.domain.embedding import EmbeddingVector
from footballpulse_intelligence_service.domain.story import (
    StoryEventType,
    StoryStatus,
)
from footballpulse_intelligence_service.domain.story_candidate_scoring import story_event_window
from footballpulse_intelligence_service.domain.story_embedding import StoryEmbeddingRecord
from footballpulse_intelligence_service.persistence.postgres_tables import (
    stories,
    story_embeddings,
    story_entities,
)


@dataclass(frozen=True, slots=True)
class CandidateQuery:
    event_type: StoryEventType
    entity_ids: tuple[UUID, ...]
    observed_at: datetime
    query_vector: EmbeddingVector
    input_builder_version: str
    model_name: str
    model_version: str
    top_k: int = 20

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("candidate observed_at must be timezone-aware")
        if not self.entity_ids:
            raise ValueError("candidate query requires canonical entities")
        if len(self.entity_ids) != len(set(self.entity_ids)):
            raise ValueError("candidate entity IDs must be unique")
        if not 1 <= self.top_k <= 20:
            raise ValueError("candidate top_k must be between 1 and 20")
        for value, field, limit in (
            (self.input_builder_version, "input_builder_version", 100),
            (self.model_name, "model_name", 200),
            (self.model_version, "model_version", 200),
        ):
            if not value.strip() or len(value) > limit:
                raise ValueError(f"candidate {field} is invalid")


@dataclass(frozen=True, slots=True)
class StoryVectorCandidate:
    story_id: UUID
    story_version: int
    status: StoryStatus
    last_seen_at: datetime
    cosine_similarity: float


@dataclass(frozen=True, slots=True)
class CandidateRetrievalResult:
    query: CandidateQuery
    candidates: tuple[StoryVectorCandidate, ...]
    missing_current_embedding_story_ids: tuple[UUID, ...]


def _embedding_values(record: StoryEmbeddingRecord) -> dict[str, object]:
    return {
        "id": record.id,
        "story_id": record.story_id,
        "story_version": record.story_version,
        "input_hash": record.input_hash,
        "input_builder_version": record.input_builder_version,
        "model_name": record.model_name,
        "model_version": record.model_version,
        "dimensions": record.dimensions,
        "embedding": list(record.vector.values),
        "token_count": record.token_count,
        "created_at": record.created_at,
    }


def _embedding_from_row(row: RowMapping) -> StoryEmbeddingRecord:
    return StoryEmbeddingRecord(
        id=row["id"],
        story_id=row["story_id"],
        story_version=row["story_version"],
        input_hash=row["input_hash"],
        input_builder_version=row["input_builder_version"],
        model_name=row["model_name"],
        model_version=row["model_version"],
        vector=EmbeddingVector.create(list(row["embedding"])),
        dimensions=row["dimensions"],
        token_count=row["token_count"],
        created_at=row["created_at"],
    )


class PostgresStoryCandidateRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def add_embedding_once(self, record: StoryEmbeddingRecord) -> StoryEmbeddingRecord:
        statement = (
            insert(story_embeddings)
            .values(**_embedding_values(record))
            .on_conflict_do_nothing(index_elements=[story_embeddings.c.id])
            .returning(*story_embeddings.c)
        )
        with self._engine.begin() as connection:
            row = connection.execute(statement).mappings().one_or_none()
            if row is None:
                row = (
                    connection.execute(
                        sa.select(story_embeddings).where(story_embeddings.c.id == record.id)
                    )
                    .mappings()
                    .one()
                )
        return _embedding_from_row(row)

    def find_candidates(self, query: CandidateQuery) -> CandidateRetrievalResult:
        hard_filters = self._hard_filters(query)
        embedding_match = sa.and_(
            story_embeddings.c.story_id == stories.c.id,
            story_embeddings.c.story_version == stories.c.version,
            story_embeddings.c.input_builder_version == query.input_builder_version,
            story_embeddings.c.model_name == query.model_name,
            story_embeddings.c.model_version == query.model_version,
        )
        distance = story_embeddings.c.embedding.cosine_distance(list(query.query_vector.values))
        candidate_statement = (
            sa.select(
                stories.c.id,
                stories.c.version,
                stories.c.status,
                stories.c.last_seen_at,
                (1 - distance).label("cosine_similarity"),
            )
            .join(story_embeddings, embedding_match)
            .where(*hard_filters)
            .order_by(distance, stories.c.id)
            .limit(query.top_k)
        )
        has_current_embedding = sa.exists(sa.select(story_embeddings.c.id).where(embedding_match))
        missing_statement = (
            sa.select(stories.c.id)
            .where(*hard_filters, ~has_current_embedding)
            .order_by(stories.c.last_seen_at.desc(), stories.c.id)
            .limit(20)
        )
        with self._engine.connect() as connection:
            rows = connection.execute(candidate_statement).mappings().all()
            missing = tuple(connection.execute(missing_statement).scalars())
        candidates = tuple(
            StoryVectorCandidate(
                story_id=row["id"],
                story_version=row["version"],
                status=StoryStatus(row["status"]),
                last_seen_at=row["last_seen_at"],
                cosine_similarity=float(row["cosine_similarity"]),
            )
            for row in rows
        )
        return CandidateRetrievalResult(query, candidates, missing)

    @staticmethod
    def _hard_filters(query: CandidateQuery) -> tuple[ColumnElement[bool], ...]:
        entity_overlap = sa.exists(
            sa.select(story_entities.c.id).where(
                story_entities.c.story_id == stories.c.id,
                story_entities.c.entity_id.in_(query.entity_ids),
            )
        )
        window_start = query.observed_at - story_event_window(query.event_type)
        return (
            stories.c.event_type == StoryEventType(query.event_type).value,
            stories.c.status != StoryStatus.CLOSED.value,
            stories.c.last_seen_at >= window_start,
            stories.c.last_seen_at <= query.observed_at,
            entity_overlap,
        )
