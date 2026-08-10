from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from footballpulse_intelligence_service.application.story_matching import (
    StoryMatchRequest,
    StoryMatchResult,
)
from footballpulse_intelligence_service.application.story_matching_worker import (
    StoryMatchingWorker,
    StoryMatchWorkRequest,
    StoryWorkStatus,
)
from footballpulse_intelligence_service.domain.delivery import ProcessedEvent
from footballpulse_intelligence_service.domain.errors import StoryConflictError
from footballpulse_intelligence_service.domain.story_candidate_decision import (
    MatchAction,
    StoryCandidateRetryableError,
    StoryMatchDecision,
)
from footballpulse_intelligence_service.domain.story_match_audit import StoryMatchAuditRecord

NOW = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
EVENT_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3cb005")


def work_request() -> StoryMatchWorkRequest:
    return StoryMatchWorkRequest(
        event_id=EVENT_ID,
        request=StoryMatchRequest(
            article_version_id=UUID("018f8b45-b634-7c81-a47d-9a7c2f3cb003"),
            input_hash="a" * 64,
            event_type="TRANSFER",
            entity_ids=(),
            primary_entity_ids=(),
            predicates=(),
            observed_at=NOW,
            query_vector=(1.0,) + (0.0,) * 383,
            input_builder_version="story-embedding-input-v1",
            embedding_model_name="BAAI/bge-small-en-v1.5",
            embedding_model_version="pinned-revision",
        ),
        received_at=NOW,
    )


class FakeMatcher:
    def __init__(self, outcome: object) -> None:
        self.outcome = outcome

    def match(self, request: StoryMatchRequest, *, now: datetime) -> StoryMatchResult:
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome  # type: ignore[no-any-return]


class FakeProcessedStore:
    def __init__(self, *, processed: bool = False) -> None:
        self.processed = processed
        self.marked: list[ProcessedEvent] = []

    def is_processed(self, consumer_name: str, event_id: UUID) -> bool:
        return self.processed

    def mark_processed(self, event: ProcessedEvent) -> None:
        self.marked.append(event)
        self.processed = True


def match_result(action: MatchAction) -> StoryMatchResult:
    decision = StoryMatchDecision(
        action=action,
        selected_story_id=None,
        selected_story_version=None,
        ranked_candidates=(),
        reason_codes=("TEST",),
        matcher_version="story-matcher-v1",
        review_threshold=55.0,
        attach_threshold=75.0,
        near_tie_margin=5.0,
        embedding_model_name="BAAI/bge-small-en-v1.5",
        embedding_model_version="pinned-revision",
    )
    audit = StoryMatchAuditRecord(
        id=UUID(int=900),
        article_version_id=UUID(int=901),
        input_hash="b" * 64,
        candidate_set_hash="c" * 64,
        action=action,
        selected_story_id=None,
        selected_story_version=None,
        review_threshold=55,
        attach_threshold=75,
        near_tie_margin=5,
        matcher_version="story-matcher-v1",
        embedding_model_name="BAAI/bge-small-en-v1.5",
        embedding_model_version="pinned-revision",
        reason_codes=("TEST",),
        candidates=(),
        created_at=NOW,
    )
    return StoryMatchResult(decision, audit)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "status"),
    [
        (MatchAction.ATTACH, StoryWorkStatus.COMPLETED_ATTACHED),
        (MatchAction.CREATE, StoryWorkStatus.COMPLETED_CREATED),
        (MatchAction.REVIEW, StoryWorkStatus.COMPLETED_REVIEW),
    ],
)
async def test_worker_maps_decision_to_explicit_work_status(
    action: MatchAction,
    status: StoryWorkStatus,
) -> None:
    result = match_result(action)
    worker = StoryMatchingWorker(FakeMatcher(result), clock=lambda: NOW)

    work = await worker.run(work_request())

    assert work.status is status
    assert work.result == result
    assert work.error_type is None


@pytest.mark.asyncio
async def test_worker_marks_known_matching_failures_retryable() -> None:
    worker = StoryMatchingWorker(
        FakeMatcher(StoryCandidateRetryableError((UUID(int=10),))), clock=lambda: NOW
    )

    work = await worker.run(work_request())

    assert work.status is StoryWorkStatus.RETRYABLE_FAILURE
    assert work.result is None
    assert work.error_type == "StoryCandidateRetryableError"
    assert work.failed_at == NOW


@pytest.mark.asyncio
async def test_worker_skips_duplicate_and_marks_successful_event_processed() -> None:
    store = FakeProcessedStore()
    worker = StoryMatchingWorker(
        FakeMatcher(match_result(MatchAction.ATTACH)),
        processed_store=store,
        consumer_name="story-matching-v1",
        clock=lambda: NOW,
    )

    work = await worker.run(work_request())

    assert work.status is StoryWorkStatus.COMPLETED_ATTACHED
    assert len(store.marked) == 1
    assert store.marked[0].consumer_name == "story-matching-v1"

    duplicate = await worker.run(work_request())
    assert duplicate.status is StoryWorkStatus.SKIPPED_DUPLICATE
    assert duplicate.result is None
    assert len(store.marked) == 1


@pytest.mark.asyncio
async def test_worker_marks_story_conflict_retryable_and_unexpected_error_failed() -> None:
    conflict = await StoryMatchingWorker(
        FakeMatcher(StoryConflictError("version changed")), clock=lambda: NOW
    ).run(work_request())
    failed = await StoryMatchingWorker(
        FakeMatcher(RuntimeError("broken")), clock=lambda: NOW
    ).run(work_request())

    assert conflict.status is StoryWorkStatus.RETRYABLE_FAILURE
    assert failed.status is StoryWorkStatus.FAILED
