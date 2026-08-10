from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
import sqlalchemy as sa
from footballpulse_intelligence_service.application.story_matching import (
    StoryCandidateContext,
    StoryMatchingOrchestrator,
    StoryMatchRequest,
)
from footballpulse_intelligence_service.domain.delivery import OutboxEvent, ProcessedEvent
from footballpulse_intelligence_service.domain.embedding import (
    EMBEDDING_DIMENSIONS,
    EmbeddingVector,
)
from footballpulse_intelligence_service.domain.entity import EntityType
from footballpulse_intelligence_service.domain.errors import StoryConflictError
from footballpulse_intelligence_service.domain.story import (
    Claim,
    ClaimEvidence,
    ClaimPredicate,
    Story,
    StoryEntity,
    StoryEventType,
    StorySource,
    StoryStatus,
)
from footballpulse_intelligence_service.domain.story_candidate_decision import (
    CandidateDecisionInput,
    StoryCandidateDecisionPolicy,
    StoryCandidatePolicyConfig,
)
from footballpulse_intelligence_service.domain.story_candidate_scoring import (
    StoryCandidateScore,
    StoryCandidateScoreComponents,
)
from footballpulse_intelligence_service.domain.story_embedding import StoryEmbeddingRecord
from footballpulse_intelligence_service.domain.story_match_audit import StoryMatchAuditRecord
from footballpulse_intelligence_service.persistence.candidate_repository import (
    CandidateQuery,
    PostgresStoryCandidateRepository,
)
from footballpulse_intelligence_service.persistence.context_repository import (
    PostgresStoryCandidateContextRepository,
)
from footballpulse_intelligence_service.persistence.match_audit_repository import (
    PostgresStoryMatchAuditRepository,
)
from footballpulse_intelligence_service.persistence.postgres_tables import (
    claims as claims_table,
)
from footballpulse_intelligence_service.persistence.postgres_tables import (
    stories,
    story_entities,
)
from footballpulse_intelligence_service.persistence.processed_event_repository import (
    PostgresProcessedEventStore,
)
from footballpulse_intelligence_service.persistence.story_repository import PostgresStoryRepository
from psycopg import sql
from sqlalchemy import create_engine

ROOT = Path(__file__).parents[3]
NOW = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
STORY_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3cb001")
ARTICLE_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3cb003")
SOURCE_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3cb004")
PLAYER_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c8101")
ARSENAL_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c8103")


def postgres_url(database: str, *, sqlalchemy_driver: bool = False) -> str:
    scheme = "postgresql+psycopg" if sqlalchemy_driver else "postgresql"
    user = os.getenv("FOOTBALLPULSE_POSTGRES_USER", "footballpulse")
    password = os.getenv("FOOTBALLPULSE_POSTGRES_PASSWORD", "footballpulse_local_only")
    host = os.getenv("FOOTBALLPULSE_POSTGRES_HOST", "127.0.0.1")
    port = os.getenv("FOOTBALLPULSE_POSTGRES_PORT", "5432")
    return f"{scheme}://{user}:{password}@{host}:{port}/{database}"


@pytest.fixture
def migrated_database() -> Iterator[str]:
    database = f"footballpulse_story_test_{uuid4().hex}"
    with psycopg.connect(postgres_url("postgres"), autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    environment = os.environ.copy()
    environment["FOOTBALLPULSE_DATABASE_URL"] = postgres_url(database, sqlalchemy_driver=True)
    migration = subprocess.run(
        [
            "uv",
            "run",
            "alembic",
            "-c",
            "services/intelligence-service/alembic.ini",
            "upgrade",
            "head",
        ],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert migration.returncode == 0, migration.stderr
    try:
        yield database
    finally:
        with psycopg.connect(postgres_url("postgres"), autocommit=True) as connection:
            connection.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (database,),
            )
            connection.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database)))


def aggregate() -> tuple[
    Story,
    StorySource,
    tuple[StoryEntity, ...],
    Claim,
    ClaimEvidence,
    ProcessedEvent,
    OutboxEvent,
]:
    story = Story.create(
        story_id=STORY_ID,
        event_type=StoryEventType.TRANSFER,
        first_seen_at=NOW,
        confidence_score=Decimal("0.6500"),
    )
    source = StorySource.create(
        link_id=UUID(int=101),
        story_id=story.id,
        article_version_id=ARTICLE_ID,
        source_id=SOURCE_ID,
        source_reliability_tier=1,
        published_at=NOW,
        observed_at=NOW,
    )
    player_entity = StoryEntity.create(
        link_id=UUID(int=102),
        story_id=story.id,
        entity_id=PLAYER_ID,
        entity_type=EntityType.PLAYER,
        now=NOW,
    )
    club_entity = StoryEntity.create(
        link_id=UUID(int=108),
        story_id=story.id,
        entity_id=ARSENAL_ID,
        entity_type=EntityType.CLUB,
        now=NOW,
    )
    claim = Claim.create(
        claim_id=UUID(int=103),
        story_id=story.id,
        subject_entity_id=ARSENAL_ID,
        predicate=ClaimPredicate.SUBMITTED_BID,
        object_entity_id=PLAYER_ID,
        object_value={"amount": 180_000_000, "currency": "EUR"},
        statement_en="Arsenal submitted a €180m bid.",
        certainty=Decimal("0.7000"),
        occurred_at=NOW,
        occurred_at_bucket=NOW,
        now=NOW,
    )
    evidence = ClaimEvidence.create(
        evidence_id=UUID(int=104),
        claim_id=claim.id,
        story_source_id=source.id,
        quote="submitted a €180m bid",
        start=8,
        end=30,
        now=NOW,
    )
    processed = ProcessedEvent.create(
        record_id=UUID(int=105),
        consumer_name="story-builder-v1",
        event_id=UUID(int=106),
        event_type="article.enriched",
        processed_at=NOW,
    )
    outbox = OutboxEvent.create(
        event_id=UUID(int=107),
        aggregate_type="STORY",
        aggregate_id=story.id,
        event_type="story.created",
        deduplication_key=f"story.created:{story.id}:1",
        payload={"story_id": str(story.id), "version": 1},
        now=NOW,
    )
    return story, source, (player_entity, club_entity), claim, evidence, processed, outbox


def test_create_rejects_untraceable_aggregate_before_opening_a_transaction() -> None:
    repository = PostgresStoryRepository(create_engine("sqlite://"))
    story, source, entity_links, claim, evidence, processed, outbox = aggregate()

    with pytest.raises(ValueError, match="source"):
        repository.create_from_event(
            story=story,
            sources=(),
            entities=entity_links,
            claims=(claim,),
            evidence=(evidence,),
            processed_event=processed,
            outbox_events=(outbox,),
        )
    with pytest.raises(ValueError, match="evidence"):
        repository.create_from_event(
            story=story,
            sources=(source,),
            entities=entity_links,
            claims=(claim,),
            evidence=(),
            processed_event=processed,
            outbox_events=(outbox,),
        )
    with pytest.raises(ValueError, match="outbox"):
        repository.create_from_event(
            story=story,
            sources=(source,),
            entities=entity_links,
            claims=(claim,),
            evidence=(evidence,),
            processed_event=processed,
            outbox_events=(),
        )
    with pytest.raises(ValueError, match="claim entity"):
        repository.create_from_event(
            story=story,
            sources=(source,),
            entities=(entity_links[0],),
            claims=(claim,),
            evidence=(evidence,),
            processed_event=processed,
            outbox_events=(outbox,),
        )


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("FOOTBALLPULSE_RUN_STORY_INTEGRATION") != "1",
    reason="set FOOTBALLPULSE_RUN_STORY_INTEGRATION=1 with PostgreSQL running",
)
def test_create_aggregate_and_replay_are_atomic_and_idempotent(
    migrated_database: str,
) -> None:
    engine = create_engine(postgres_url(migrated_database, sqlalchemy_driver=True))
    repository = PostgresStoryRepository(engine)
    story, source, entity_links, claim, evidence, processed, outbox = aggregate()

    assert repository.create_from_event(
        story=story,
        sources=(source,),
        entities=entity_links,
        claims=(claim,),
        evidence=(evidence,),
        processed_event=processed,
        outbox_events=(outbox,),
    ) is True
    assert repository.create_from_event(
        story=story,
        sources=(source,),
        entities=entity_links,
        claims=(claim,),
        evidence=(evidence,),
        processed_event=processed,
        outbox_events=(outbox,),
    ) is False

    with engine.connect() as connection:
        counts = connection.execute(
            sa.text(
                "SELECT "
                "(SELECT count(*) FROM intelligence_schema.stories), "
                "(SELECT count(*) FROM intelligence_schema.story_sources), "
                "(SELECT count(*) FROM intelligence_schema.story_entities), "
                "(SELECT count(*) FROM intelligence_schema.claims), "
                "(SELECT count(*) FROM intelligence_schema.claim_evidence), "
                "(SELECT count(*) FROM intelligence_schema.processed_events), "
                "(SELECT count(*) FROM intelligence_schema.outbox_events)"
            )
        ).one()
    assert counts == (1, 1, 2, 1, 1, 1, 1)
    engine.dispose()


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("FOOTBALLPULSE_RUN_STORY_INTEGRATION") != "1",
    reason="set FOOTBALLPULSE_RUN_STORY_INTEGRATION=1 with PostgreSQL running",
)
def test_optimistic_update_commits_atomically_and_stale_update_rolls_back_marker(
    migrated_database: str,
) -> None:
    engine = create_engine(postgres_url(migrated_database, sqlalchemy_driver=True))
    repository = PostgresStoryRepository(engine)
    story, source, entity_links, claim, evidence, processed, outbox = aggregate()
    repository.create_from_event(
        story=story,
        sources=(source,),
        entities=entity_links,
        claims=(claim,),
        evidence=(evidence,),
        processed_event=processed,
        outbox_events=(outbox,),
    )

    updated = story.observe(at=NOW + timedelta(hours=6), confidence_score=Decimal("0.8000"))
    update_marker = ProcessedEvent.create(
        record_id=UUID(int=201),
        consumer_name="story-builder-v1",
        event_id=UUID(int=202),
        event_type="article.enriched",
        processed_at=NOW + timedelta(hours=6),
    )
    update_outbox = OutboxEvent.create(
        event_id=UUID(int=203),
        aggregate_type="STORY",
        aggregate_id=story.id,
        event_type="story.updated",
        deduplication_key=f"story.updated:{story.id}:2",
        payload={"story_id": str(story.id), "version": 2},
        now=NOW + timedelta(hours=6),
    )

    assert repository.update_from_event(
        story=updated,
        expected_version=1,
        sources=(),
        entities=(),
        claims=(),
        evidence=(),
        processed_event=update_marker,
        outbox_events=(update_outbox,),
    ) is True
    assert repository.get(story.id) == updated

    stale = replace(
        updated,
        status=StoryStatus.CONFIRMED,
        updated_at=NOW + timedelta(hours=12),
    )
    stale_marker = ProcessedEvent.create(
        record_id=UUID(int=204),
        consumer_name="story-builder-v1",
        event_id=UUID(int=205),
        event_type="article.enriched",
        processed_at=NOW + timedelta(hours=12),
    )
    stale_outbox = OutboxEvent.create(
        event_id=UUID(int=206),
        aggregate_type="STORY",
        aggregate_id=story.id,
        event_type="story.updated",
        deduplication_key=f"story.updated:{story.id}:3",
        payload={"story_id": str(story.id), "version": 3},
        now=NOW + timedelta(hours=12),
    )
    with pytest.raises(StoryConflictError, match="version"):
        repository.update_from_event(
            story=stale,
            expected_version=1,
            sources=(),
            entities=(),
            claims=(),
            evidence=(),
            processed_event=stale_marker,
            outbox_events=(stale_outbox,),
        )

    with engine.connect() as connection:
        stale_marker_count = connection.execute(
            sa.text(
                "SELECT count(*) FROM intelligence_schema.processed_events WHERE event_id = :id"
            ),
            {"id": stale_marker.event_id},
        ).scalar_one()
        outbox_count = connection.execute(
            sa.text("SELECT count(*) FROM intelligence_schema.outbox_events")
        ).scalar_one()
    assert stale_marker_count == 0
    assert outbox_count == 2
    engine.dispose()


@pytest.mark.integration
@pytest.mark.parametrize("duplicate_kind", ["source", "entity", "claim", "evidence"])
@pytest.mark.skipif(
    os.getenv("FOOTBALLPULSE_RUN_STORY_INTEGRATION") != "1",
    reason="set FOOTBALLPULSE_RUN_STORY_INTEGRATION=1 with PostgreSQL running",
)
def test_unique_aggregate_link_conflict_rolls_back_event_and_story_version(
    migrated_database: str,
    duplicate_kind: str,
) -> None:
    engine = create_engine(postgres_url(migrated_database, sqlalchemy_driver=True))
    repository = PostgresStoryRepository(engine)
    story, source, entity_links, claim, evidence, processed, outbox = aggregate()
    repository.create_from_event(
        story=story,
        sources=(source,),
        entities=entity_links,
        claims=(claim,),
        evidence=(evidence,),
        processed_event=processed,
        outbox_events=(outbox,),
    )
    updated = story.observe(at=NOW + timedelta(hours=6), confidence_score=Decimal("0.7000"))
    conflict_marker = ProcessedEvent.create(
        record_id=uuid4(),
        consumer_name="story-builder-v1",
        event_id=uuid4(),
        event_type="article.enriched",
        processed_at=NOW + timedelta(hours=6),
    )
    conflict_outbox = OutboxEvent.create(
        event_id=uuid4(),
        aggregate_type="STORY",
        aggregate_id=story.id,
        event_type="story.updated",
        deduplication_key=f"conflict:{duplicate_kind}:{story.id}",
        payload={"story_id": str(story.id), "version": 2},
        now=NOW + timedelta(hours=6),
    )
    duplicate_source = replace(source, id=uuid4())
    duplicate_entity = replace(entity_links[0], id=uuid4())
    duplicate_claim = replace(claim, id=uuid4())
    duplicate_evidence = replace(evidence, id=uuid4())
    deltas = {
        "source": ((duplicate_source,), (), (), ()),
        "entity": ((), (duplicate_entity,), (), ()),
        "claim": ((), (), (duplicate_claim,), ()),
        "evidence": ((), (), (), (duplicate_evidence,)),
    }
    new_sources, new_entities, new_claims, new_evidence = deltas[duplicate_kind]

    with pytest.raises(StoryConflictError, match="conflicts"):
        repository.update_from_event(
            story=updated,
            expected_version=1,
            sources=new_sources,
            entities=new_entities,
            claims=new_claims,
            evidence=new_evidence,
            processed_event=conflict_marker,
            outbox_events=(conflict_outbox,),
        )

    assert repository.get(story.id) == story
    with engine.connect() as connection:
        marker_count = connection.execute(
            sa.text(
                "SELECT count(*) FROM intelligence_schema.processed_events WHERE event_id = :id"
            ),
            {"id": conflict_marker.event_id},
        ).scalar_one()
        outbox_count = connection.execute(
            sa.text(
                "SELECT count(*) FROM intelligence_schema.outbox_events "
                "WHERE deduplication_key = :key"
            ),
            {"key": conflict_outbox.deduplication_key},
        ).scalar_one()
    assert marker_count == 0
    assert outbox_count == 0
    engine.dispose()


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("FOOTBALLPULSE_RUN_STORY_INTEGRATION") != "1",
    reason="set FOOTBALLPULSE_RUN_STORY_INTEGRATION=1 with PostgreSQL running",
)
def test_candidate_repository_hard_filters_current_embeddings_and_orders_exact_top_k(
    migrated_database: str,
) -> None:
    engine = create_engine(postgres_url(migrated_database, sqlalchemy_driver=True))
    repository = PostgresStoryCandidateRepository(engine)
    same_vector = EmbeddingVector.create([1.0] + [0.0] * (EMBEDDING_DIMENSIONS - 1))
    distant_vector = EmbeddingVector.create([0.0, 1.0] + [0.0] * (EMBEDDING_DIMENSIONS - 2))
    story_ids = {
        name: UUID(int=300 + index)
        for index, name in enumerate(
            ("best", "stale", "injury", "closed", "old", "no_overlap", "missing")
        )
    }

    def story_row(
        name: str,
        *,
        event_type: str = "TRANSFER",
        status: str = "DEVELOPING",
        age_days: int = 1,
        version: int = 1,
    ) -> dict[str, object]:
        observed = NOW - timedelta(days=age_days)
        return {
            "id": story_ids[name],
            "event_type": event_type,
            "status": status,
            "confidence_score": Decimal("0.5000"),
            "first_seen_at": observed,
            "last_seen_at": observed,
            "version": version,
            "created_at": observed,
            "updated_at": observed,
        }

    rows = [
        story_row("best"),
        story_row("stale", status="STALE", age_days=20),
        story_row("injury", event_type="INJURY"),
        story_row("closed", status="CLOSED"),
        story_row("old", age_days=31),
        story_row("no_overlap"),
        story_row("missing", version=2),
    ]
    entity_rows = [
        {
            "id": uuid4(),
            "story_id": row["id"],
            "entity_id": ARSENAL_ID if row["id"] == story_ids["no_overlap"] else PLAYER_ID,
            "entity_type": "CLUB" if row["id"] == story_ids["no_overlap"] else "PLAYER",
            "created_at": row["created_at"],
        }
        for row in rows
    ]
    with engine.begin() as connection:
        connection.execute(stories.insert(), rows)
        connection.execute(story_entities.insert(), entity_rows)

    def embedding(name: str, vector: EmbeddingVector, *, story_version: int = 1) -> None:
        repository.add_embedding_once(
            StoryEmbeddingRecord.create(
                story_id=story_ids[name],
                story_version=story_version,
                input_hash=(f"{story_ids[name].int:064x}")[-64:],
                input_builder_version="story-embedding-input-v1",
                model_name="BAAI/bge-small-en-v1.5",
                model_version="pinned-revision",
                vector=vector,
                token_count=20,
                now=NOW,
            )
        )

    for name in ("best", "injury", "closed", "old", "no_overlap", "missing"):
        embedding(name, same_vector)
    embedding("stale", distant_vector)

    result = repository.find_candidates(
        CandidateQuery(
            event_type=StoryEventType.TRANSFER,
            entity_ids=(PLAYER_ID,),
            observed_at=NOW,
            query_vector=same_vector,
            input_builder_version="story-embedding-input-v1",
            model_name="BAAI/bge-small-en-v1.5",
            model_version="pinned-revision",
            top_k=20,
        )
    )

    assert [candidate.story_id for candidate in result.candidates] == [
        story_ids["best"],
        story_ids["stale"],
    ]
    assert result.candidates[0].cosine_similarity == pytest.approx(1.0)
    assert result.missing_current_embedding_story_ids == (story_ids["missing"],)

    top_one = repository.find_candidates(replace(result.query, top_k=1))
    assert [candidate.story_id for candidate in top_one.candidates] == [story_ids["best"]]
    engine.dispose()


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("FOOTBALLPULSE_RUN_STORY_INTEGRATION") != "1",
    reason="set FOOTBALLPULSE_RUN_STORY_INTEGRATION=1 with PostgreSQL running",
)
def test_match_audit_repository_persists_ranked_decision_idempotently(
    migrated_database: str,
) -> None:
    engine = create_engine(postgres_url(migrated_database, sqlalchemy_driver=True))
    repository = PostgresStoryMatchAuditRepository(engine)
    score = StoryCandidateScore(
        81.5,
        StoryCandidateScoreComponents(24.0, 25.0, 7.5, 20.0, 5.0),
        ("PRIMARY_ENTITY_MATCH", "PREDICATE_PROGRESSION"),
    )
    decision = StoryCandidateDecisionPolicy(
        StoryCandidatePolicyConfig(55.0, 75.0, 5.0, "story-matcher-v1")
    ).decide(
        candidates=(CandidateDecisionInput(STORY_ID, 3, score),),
        missing_current_embedding_story_ids=(),
        embedding_model_name="BAAI/bge-small-en-v1.5",
        embedding_model_version="pinned-revision",
    )
    audit = StoryMatchAuditRecord.create(
        article_version_id=ARTICLE_ID,
        input_hash="a" * 64,
        decision=decision,
        now=NOW,
    )

    assert repository.add_once(audit) == audit
    assert repository.add_once(audit) == audit
    assert repository.get(audit.id) == audit

    with engine.connect() as connection:
        decision_count = connection.execute(
            sa.text(
                "SELECT count(*) FROM intelligence_schema.story_match_decisions "
                "WHERE id = :id"
            ),
            {"id": audit.id},
        ).scalar_one()
        candidate_count = connection.execute(
            sa.text(
                "SELECT count(*) FROM intelligence_schema.story_match_candidate_scores "
                "WHERE decision_id = :id"
            ),
            {"id": audit.id},
        ).scalar_one()
    assert (decision_count, candidate_count) == (1, 1)

    broken_id = UUID(int=999)
    broken_candidate = replace(
        audit.candidates[0],
        id=UUID(int=998),
        decision_id=broken_id,
        total_score=Decimal("101.000"),
    )
    broken_audit = replace(
        audit,
        id=broken_id,
        input_hash="b" * 64,
        candidate_set_hash="c" * 64,
        candidates=(broken_candidate,),
    )
    with pytest.raises(sa.exc.IntegrityError):
        repository.add_once(broken_audit)
    with engine.connect() as connection:
        rolled_back = connection.execute(
            sa.text(
                "SELECT count(*) FROM intelligence_schema.story_match_decisions "
                "WHERE id = :id"
            ),
            {"id": broken_id},
        ).scalar_one()
    assert rolled_back == 0
    engine.dispose()


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("FOOTBALLPULSE_RUN_STORY_INTEGRATION") != "1",
    reason="set FOOTBALLPULSE_RUN_STORY_INTEGRATION=1 with PostgreSQL running",
)
def test_context_repository_loads_current_story_entities_and_predicates(
    migrated_database: str,
) -> None:
    engine = create_engine(postgres_url(migrated_database, sqlalchemy_driver=True))
    repository = PostgresStoryCandidateContextRepository(engine)
    story_id = UUID(int=700)
    with engine.begin() as connection:
        connection.execute(
            stories.insert(),
            {
                "id": story_id,
                "event_type": "TRANSFER",
                "status": "DEVELOPING",
                "confidence_score": Decimal("0.5000"),
                "first_seen_at": NOW,
                "last_seen_at": NOW,
                "version": 4,
                "created_at": NOW,
                "updated_at": NOW,
            },
        )
        connection.execute(
            story_entities.insert(),
            [
                {
                    "id": UUID(int=701),
                    "story_id": story_id,
                    "entity_id": PLAYER_ID,
                    "entity_type": "PLAYER",
                    "created_at": NOW,
                },
                {
                    "id": UUID(int=702),
                    "story_id": story_id,
                    "entity_id": ARSENAL_ID,
                    "entity_type": "CLUB",
                    "created_at": NOW,
                },
            ],
        )
        connection.execute(
            claims_table.insert(),
            {
                "id": UUID(int=703),
                "story_id": story_id,
                "claim_fingerprint": "b" * 64,
                "subject_entity_id": ARSENAL_ID,
                "predicate": "CONTACTED",
                "object_entity_id": PLAYER_ID,
                "object_value": None,
                "statement_en": "Arsenal contacted Vinicius",
                "certainty": Decimal("0.5000"),
                "occurred_at": NOW,
                "occurred_at_bucket": NOW,
                "created_at": NOW,
            },
        )

    contexts = repository.load_current((story_id,))

    assert contexts == (
        StoryCandidateContext(
            story_id=story_id,
            story_version=4,
            primary_entity_ids=(PLAYER_ID,),
            entity_ids=(PLAYER_ID, ARSENAL_ID),
            predicates=(ClaimPredicate.CONTACTED,),
        ),
    )
    engine.dispose()


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("FOOTBALLPULSE_RUN_STORY_INTEGRATION") != "1",
    reason="set FOOTBALLPULSE_RUN_STORY_INTEGRATION=1 with PostgreSQL running",
)
def test_story_matching_orchestration_runs_end_to_end_with_postgres(
    migrated_database: str,
) -> None:
    engine = create_engine(postgres_url(migrated_database, sqlalchemy_driver=True))
    story_id = UUID(int=800)
    with engine.begin() as connection:
        connection.execute(
            stories.insert(),
            {
                "id": story_id,
                "event_type": "TRANSFER",
                "status": "DEVELOPING",
                "confidence_score": Decimal("0.5000"),
                "first_seen_at": NOW,
                "last_seen_at": NOW,
                "version": 1,
                "created_at": NOW,
                "updated_at": NOW,
            },
        )
        connection.execute(
            story_entities.insert(),
            [
                {
                    "id": UUID(int=801),
                    "story_id": story_id,
                    "entity_id": PLAYER_ID,
                    "entity_type": "PLAYER",
                    "created_at": NOW,
                },
                {
                    "id": UUID(int=802),
                    "story_id": story_id,
                    "entity_id": ARSENAL_ID,
                    "entity_type": "CLUB",
                    "created_at": NOW,
                },
            ],
        )
        connection.execute(
            claims_table.insert(),
            {
                "id": UUID(int=803),
                "story_id": story_id,
                "claim_fingerprint": "d" * 64,
                "subject_entity_id": ARSENAL_ID,
                "predicate": "CONTACTED",
                "object_entity_id": PLAYER_ID,
                "object_value": None,
                "statement_en": "Arsenal contacted Vinicius",
                "certainty": Decimal("0.5000"),
                "occurred_at": NOW,
                "occurred_at_bucket": NOW,
                "created_at": NOW,
            },
        )
    vector = EmbeddingVector.create([1.0] + [0.0] * (EMBEDDING_DIMENSIONS - 1))
    candidate_repository = PostgresStoryCandidateRepository(engine)
    candidate_repository.add_embedding_once(
        StoryEmbeddingRecord.create(
            story_id=story_id,
            story_version=1,
            input_hash="e" * 64,
            input_builder_version="story-embedding-input-v1",
            model_name="BAAI/bge-small-en-v1.5",
            model_version="pinned-revision",
            vector=vector,
            token_count=20,
            now=NOW,
        )
    )
    orchestrator = StoryMatchingOrchestrator(
        candidate_repository=candidate_repository,
        context_repository=PostgresStoryCandidateContextRepository(engine),
        audit_repository=PostgresStoryMatchAuditRepository(engine),
        policy=StoryCandidateDecisionPolicy(
            StoryCandidatePolicyConfig(55.0, 75.0, 5.0, "story-matcher-v1")
        ),
    )

    result = orchestrator.match(
        StoryMatchRequest(
            article_version_id=UUID(int=804),
            input_hash="f" * 64,
            event_type=StoryEventType.TRANSFER,
            entity_ids=(PLAYER_ID, ARSENAL_ID),
            primary_entity_ids=(PLAYER_ID,),
            predicates=(ClaimPredicate.SUBMITTED_BID,),
            observed_at=NOW,
            query_vector=tuple(vector.values),
            input_builder_version="story-embedding-input-v1",
            embedding_model_name="BAAI/bge-small-en-v1.5",
            embedding_model_version="pinned-revision",
        ),
        now=NOW,
    )

    assert result.decision.action.value == "ATTACH"
    assert result.decision.selected_story_id == story_id
    assert result.audit.selected_story_id == story_id
    with engine.connect() as connection:
        count = connection.execute(
            sa.text(
                "SELECT count(*) FROM intelligence_schema.story_match_decisions "
                "WHERE id = :id"
            ),
            {"id": result.audit.id},
        ).scalar_one()
    assert count == 1
    engine.dispose()


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("FOOTBALLPULSE_RUN_STORY_INTEGRATION") != "1",
    reason="set FOOTBALLPULSE_RUN_STORY_INTEGRATION=1 with PostgreSQL running",
)
def test_processed_event_store_is_idempotent(migrated_database: str) -> None:
    engine = create_engine(postgres_url(migrated_database, sqlalchemy_driver=True))
    store = PostgresProcessedEventStore(engine)
    event = ProcessedEvent.create(
        record_id=UUID(int=950),
        consumer_name="story-matching-v1",
        event_id=UUID(int=951),
        event_type="story.match.v1",
        processed_at=NOW,
    )

    assert store.is_processed(event.consumer_name, event.event_id) is False
    assert store.mark_processed(event) is True
    assert store.is_processed(event.consumer_name, event.event_id) is True
    assert store.mark_processed(event) is False
    engine.dispose()
