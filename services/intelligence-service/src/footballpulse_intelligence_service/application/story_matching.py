from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from footballpulse_intelligence_service.domain.embedding import EmbeddingVector
from footballpulse_intelligence_service.domain.story import ClaimPredicate, StoryEventType
from footballpulse_intelligence_service.domain.story_candidate_decision import (
    CandidateDecisionInput,
    StoryCandidateDecisionPolicy,
    StoryMatchDecision,
)
from footballpulse_intelligence_service.domain.story_candidate_scoring import (
    StoryCandidateScoreInput,
    score_story_candidate,
)
from footballpulse_intelligence_service.domain.story_match_audit import StoryMatchAuditRecord
from footballpulse_intelligence_service.persistence.candidate_repository import (
    CandidateQuery,
    CandidateRetrievalResult,
    StoryVectorCandidate,
)


@dataclass(frozen=True, slots=True)
class StoryMatchRequest:
    article_version_id: UUID
    input_hash: str
    event_type: StoryEventType
    entity_ids: tuple[UUID, ...]
    primary_entity_ids: tuple[UUID, ...]
    predicates: tuple[ClaimPredicate, ...]
    observed_at: datetime
    query_vector: tuple[float, ...]
    input_builder_version: str
    embedding_model_name: str
    embedding_model_version: str


@dataclass(frozen=True, slots=True)
class StoryCandidateContext:
    story_id: UUID
    story_version: int
    primary_entity_ids: tuple[UUID, ...]
    entity_ids: tuple[UUID, ...]
    predicates: tuple[ClaimPredicate, ...]


class StoryCandidateContextRepository(Protocol):
    def load_current(self, story_ids: tuple[UUID, ...]) -> tuple[StoryCandidateContext, ...]: ...


class StoryCandidateRepository(Protocol):
    def find_candidates(self, query: CandidateQuery) -> CandidateRetrievalResult: ...


class StoryMatchAuditRepository(Protocol):
    def add_once(self, record: StoryMatchAuditRecord) -> StoryMatchAuditRecord: ...


class StoryMatchContextRetryableError(Exception):
    def __init__(self, story_ids: tuple[UUID, ...]) -> None:
        self.story_ids = story_ids
        super().__init__("current Story matching context is missing; retry after loading it")


@dataclass(frozen=True, slots=True)
class StoryMatchResult:
    decision: StoryMatchDecision
    audit: StoryMatchAuditRecord


class StoryMatchingOrchestrator:
    def __init__(
        self,
        *,
        candidate_repository: StoryCandidateRepository,
        context_repository: StoryCandidateContextRepository,
        audit_repository: StoryMatchAuditRepository,
        policy: StoryCandidateDecisionPolicy,
    ) -> None:
        self._candidate_repository = candidate_repository
        self._context_repository = context_repository
        self._audit_repository = audit_repository
        self._policy = policy

    def match(self, request: StoryMatchRequest, *, now: datetime) -> StoryMatchResult:
        vector = EmbeddingVector.create(request.query_vector)
        retrieval = self._candidate_repository.find_candidates(
            CandidateQuery(
                event_type=request.event_type,
                entity_ids=request.entity_ids,
                observed_at=request.observed_at,
                query_vector=vector,
                input_builder_version=request.input_builder_version,
                model_name=request.embedding_model_name,
                model_version=request.embedding_model_version,
            )
        )
        if retrieval.missing_current_embedding_story_ids:
            return self._decide_with_policy(
                request,
                retrieval,
                candidates=(),
                now=now,
            )
        contexts = self._load_contexts(retrieval.candidates)
        candidate_inputs = tuple(
            self._score(request, candidate, contexts[candidate.story_id])
            for candidate in retrieval.candidates
        )
        return self._decide_with_policy(request, retrieval, candidates=candidate_inputs, now=now)

    def _load_contexts(
        self, candidates: tuple[StoryVectorCandidate, ...]
    ) -> dict[UUID, StoryCandidateContext]:
        story_ids = tuple(candidate.story_id for candidate in candidates)
        loaded = self._context_repository.load_current(story_ids)
        contexts = {context.story_id: context for context in loaded}
        missing = tuple(story_id for story_id in story_ids if story_id not in contexts)
        version_mismatch = tuple(
            candidate.story_id
            for candidate in candidates
            if candidate.story_id in contexts
            and contexts[candidate.story_id].story_version != candidate.story_version
        )
        retry_ids = tuple(dict.fromkeys((*missing, *version_mismatch)))
        if retry_ids:
            raise StoryMatchContextRetryableError(retry_ids)
        return contexts

    @staticmethod
    def _score(
        request: StoryMatchRequest,
        candidate: StoryVectorCandidate,
        context: StoryCandidateContext,
    ) -> CandidateDecisionInput:
        score = score_story_candidate(
            StoryCandidateScoreInput(
                event_type=request.event_type,
                cosine_similarity=candidate.cosine_similarity,
                query_primary_entity_ids=request.primary_entity_ids,
                candidate_primary_entity_ids=context.primary_entity_ids,
                query_entity_ids=request.entity_ids,
                candidate_entity_ids=context.entity_ids,
                query_predicates=request.predicates,
                candidate_predicates=context.predicates,
                observed_at=request.observed_at,
                candidate_last_seen_at=candidate.last_seen_at,
            )
        )
        return CandidateDecisionInput(candidate.story_id, candidate.story_version, score)

    def _decide_with_policy(
        self,
        request: StoryMatchRequest,
        retrieval: CandidateRetrievalResult,
        *,
        candidates: tuple[CandidateDecisionInput, ...],
        now: datetime,
    ) -> StoryMatchResult:
        decision = self._policy.decide(
            candidates=candidates,
            missing_current_embedding_story_ids=retrieval.missing_current_embedding_story_ids,
            embedding_model_name=request.embedding_model_name,
            embedding_model_version=request.embedding_model_version,
        )
        audit = self._audit_repository.add_once(
            StoryMatchAuditRecord.create(
                article_version_id=request.article_version_id,
                input_hash=request.input_hash,
                decision=decision,
                now=now,
            )
        )
        return StoryMatchResult(decision, audit)
