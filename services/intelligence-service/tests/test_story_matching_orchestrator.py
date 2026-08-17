from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from footballpulse_intelligence_service.application.story_matching import (
    StoryCandidateContext,
    StoryMatchContextRetryableError,
    StoryMatchingOrchestrator,
    StoryMatchRequest,
)
from footballpulse_intelligence_service.domain.delivery import ProcessedEvent
from footballpulse_intelligence_service.domain.embedding import EmbeddingVector
from footballpulse_intelligence_service.domain.story import (
    ClaimPredicate,
    StoryEventType,
    StoryStatus,
)
from footballpulse_intelligence_service.domain.story_candidate_decision import (
    StoryCandidateDecisionPolicy,
    StoryCandidatePolicyConfig,
    StoryCandidateRetryableError,
)
from footballpulse_intelligence_service.domain.story_match_audit import StoryMatchAuditRecord
from footballpulse_intelligence_service.persistence.candidate_repository import (
    CandidateQuery,
    CandidateRetrievalResult,
    StoryVectorCandidate,
)

ARTICLE_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3cb003")
STORY_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3cb001")
PLAYER_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c8101")
ARSENAL_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c8103")
NOW = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)


class FakeCandidateRepository:
    def __init__(self, result: CandidateRetrievalResult) -> None:
        self.result = result
        self.received: CandidateQuery | None = None

    def find_candidates(self, query: CandidateQuery) -> CandidateRetrievalResult:
        self.received = query
        return self.result


class FakeContextRepository:
    def __init__(self, contexts: tuple[StoryCandidateContext, ...]) -> None:
        self.contexts = contexts

    def load_current(self, story_ids: tuple[UUID, ...]) -> tuple[StoryCandidateContext, ...]:
        return tuple(context for context in self.contexts if context.story_id in story_ids)


class FakeAuditRepository:
    def __init__(self) -> None:
        self.records: list[StoryMatchAuditRecord] = []

    def add_once(self, record: StoryMatchAuditRecord) -> StoryMatchAuditRecord:
        self.records.append(record)
        return record


class FakeCommitRepository:
    def __init__(self) -> None:
        self.calls: list[tuple[StoryMatchAuditRecord, ProcessedEvent]] = []

    def commit(self, record: StoryMatchAuditRecord, event: ProcessedEvent) -> StoryMatchAuditRecord:
        self.calls.append((record, event))
        return record


def request() -> StoryMatchRequest:
    return StoryMatchRequest(
        article_version_id=ARTICLE_ID,
        input_hash="a" * 64,
        event_type=StoryEventType.TRANSFER,
        entity_ids=(PLAYER_ID, ARSENAL_ID),
        primary_entity_ids=(PLAYER_ID,),
        predicates=(ClaimPredicate.SUBMITTED_BID,),
        observed_at=NOW,
        query_vector=(1.0,) + (0.0,) * 383,
        input_builder_version="story-embedding-input-v1",
        embedding_model_name="BAAI/bge-small-en-v1.5",
        embedding_model_version="pinned-revision",
    )


def context() -> StoryCandidateContext:
    return StoryCandidateContext(
        story_id=STORY_ID,
        story_version=3,
        primary_entity_ids=(PLAYER_ID,),
        entity_ids=(PLAYER_ID, ARSENAL_ID),
        predicates=(ClaimPredicate.CONTACTED,),
    )


def candidate_query() -> CandidateQuery:
    return CandidateQuery(
        event_type=StoryEventType.TRANSFER,
        entity_ids=(PLAYER_ID, ARSENAL_ID),
        observed_at=NOW,
        query_vector=EmbeddingVector.create([1.0] + [0.0] * 383),
        input_builder_version="story-embedding-input-v1",
        model_name="BAAI/bge-small-en-v1.5",
        model_version="pinned-revision",
    )


def test_orchestrator_retrieves_scores_decides_and_persists_audit() -> None:
    query = candidate_query()
    candidate = StoryVectorCandidate(STORY_ID, 3, StoryStatus.DEVELOPING, NOW, 1.0)
    retrieval = CandidateRetrievalResult(query, (candidate,), ())
    candidates = FakeCandidateRepository(retrieval)
    audit = FakeAuditRepository()
    orchestrator = StoryMatchingOrchestrator(
        candidate_repository=candidates,
        context_repository=FakeContextRepository((context(),)),
        audit_repository=audit,
        policy=StoryCandidateDecisionPolicy(
            StoryCandidatePolicyConfig(55.0, 75.0, 5.0, "story-matcher-v1")
        ),
    )

    result = orchestrator.match(request(), now=NOW)

    assert result.decision.action.value == "ATTACH"
    assert result.decision.selected_story_id == STORY_ID
    assert len(audit.records) == 1
    assert candidates.received is not None
    assert candidates.received.entity_ids == (PLAYER_ID, ARSENAL_ID)


def test_orchestrator_does_not_create_audit_when_context_is_missing() -> None:
    retrieval = CandidateRetrievalResult(
        query=candidate_query(),
        candidates=(StoryVectorCandidate(STORY_ID, 3, StoryStatus.DEVELOPING, NOW, 1.0),),
        missing_current_embedding_story_ids=(),
    )
    audit = FakeAuditRepository()
    orchestrator = StoryMatchingOrchestrator(
        candidate_repository=FakeCandidateRepository(retrieval),
        context_repository=FakeContextRepository(()),
        audit_repository=audit,
        policy=StoryCandidateDecisionPolicy(
            StoryCandidatePolicyConfig(55.0, 75.0, 5.0, "story-matcher-v1")
        ),
    )

    with pytest.raises(StoryMatchContextRetryableError):
        orchestrator.match(request(), now=NOW)
    assert audit.records == []


def test_orchestrator_uses_atomic_commit_when_processed_event_is_supplied() -> None:
    query = candidate_query()
    candidate = StoryVectorCandidate(STORY_ID, 3, StoryStatus.DEVELOPING, NOW, 1.0)
    commit = FakeCommitRepository()
    orchestrator = StoryMatchingOrchestrator(
        candidate_repository=FakeCandidateRepository(
            CandidateRetrievalResult(query, (candidate,), ())
        ),
        context_repository=FakeContextRepository((context(),)),
        audit_repository=FakeAuditRepository(),
        commit_repository=commit,
        policy=StoryCandidateDecisionPolicy(
            StoryCandidatePolicyConfig(55.0, 75.0, 5.0, "story-matcher-v1")
        ),
    )
    event = ProcessedEvent.create(
        record_id=UUID(int=600),
        consumer_name="story-matching-v1",
        event_id=UUID(int=601),
        event_type="story.match.v1",
        processed_at=NOW,
    )

    result = orchestrator.match(request(), now=NOW, processed_event=event)

    assert result.audit == commit.calls[0][0]
    assert commit.calls[0][1] == event


def test_orchestrator_propagates_missing_embedding_retry_without_audit() -> None:
    retrieval = CandidateRetrievalResult(
        query=candidate_query(),
        candidates=(),
        missing_current_embedding_story_ids=(STORY_ID,),
    )
    audit = FakeAuditRepository()
    orchestrator = StoryMatchingOrchestrator(
        candidate_repository=FakeCandidateRepository(retrieval),
        context_repository=FakeContextRepository(()),
        audit_repository=audit,
        policy=StoryCandidateDecisionPolicy(
            StoryCandidatePolicyConfig(55.0, 75.0, 5.0, "story-matcher-v1")
        ),
    )

    with pytest.raises(StoryCandidateRetryableError):
        orchestrator.match(request(), now=NOW)
    assert audit.records == []
