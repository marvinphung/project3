from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from footballpulse_runtime_config import bind_log_context, log_event

from footballpulse_intelligence_service.application.story_matching import (
    StoryMatchContextRetryableError,
    StoryMatchRequest,
    StoryMatchResult,
)
from footballpulse_intelligence_service.domain.delivery import ProcessedEvent
from footballpulse_intelligence_service.domain.errors import StoryConflictError
from footballpulse_intelligence_service.domain.story_candidate_decision import (
    MatchAction,
    StoryCandidateRetryableError,
)

LOGGER = logging.getLogger("footballpulse.intelligence.story_matching")


class StoryMatcher(Protocol):
    def match(
        self,
        request: StoryMatchRequest,
        *,
        now: datetime,
        processed_event: ProcessedEvent | None = None,
    ) -> StoryMatchResult: ...


class ProcessedEventStore(Protocol):
    def is_processed(self, consumer_name: str, event_id: UUID) -> bool: ...

    def mark_processed(self, event: ProcessedEvent) -> None: ...


class StoryWorkStatus(StrEnum):
    COMPLETED_ATTACHED = "COMPLETED_ATTACHED"
    COMPLETED_CREATED = "COMPLETED_CREATED"
    COMPLETED_REVIEW = "COMPLETED_REVIEW"
    SKIPPED_DUPLICATE = "SKIPPED_DUPLICATE"
    RETRYABLE_FAILURE = "RETRYABLE_FAILURE"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class StoryMatchWorkRequest:
    event_id: UUID
    request: StoryMatchRequest
    received_at: datetime


@dataclass(frozen=True, slots=True)
class StoryWorkResult:
    event_id: UUID
    status: StoryWorkStatus
    result: StoryMatchResult | None
    error_type: str | None
    failed_at: datetime | None


class StoryMatchingWorker:
    def __init__(
        self,
        matcher: StoryMatcher,
        *,
        processed_store: ProcessedEventStore | None = None,
        consumer_name: str = "story-matching-v1",
        max_concurrency: int = 1,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if not 1 <= max_concurrency <= 2:
            raise ValueError("Story matching concurrency must be between 1 and 2")
        self._matcher = matcher
        self._processed_store = processed_store
        self._consumer_name = consumer_name
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._clock = clock

    async def run(self, request: StoryMatchWorkRequest) -> StoryWorkResult:
        started = time.monotonic()
        async with self._semaphore:
            with bind_log_context(correlation_id=str(request.event_id)):
                log_event(
                    LOGGER,
                    "story_matching_started",
                    event_id=str(request.event_id),
                )
                if self._processed_store is not None and self._processed_store.is_processed(
                    self._consumer_name, request.event_id
                ):
                    log_event(
                        LOGGER,
                        "story_matching_duplicate_skipped",
                        event_id=str(request.event_id),
                    )
                    return StoryWorkResult(
                        request.event_id,
                        StoryWorkStatus.SKIPPED_DUPLICATE,
                        None,
                        None,
                        None,
                    )
            try:
                processed_event = (
                    ProcessedEvent.create(
                        record_id=request.event_id,
                        consumer_name=self._consumer_name,
                        event_id=request.event_id,
                        event_type="story.match.v1",
                        processed_at=self._clock(),
                    )
                    if self._processed_store is not None
                    else None
                )
                if getattr(self._matcher, "handles_processed_events", False):
                    result = self._matcher.match(
                        request.request,
                        now=self._clock(),
                        processed_event=processed_event,
                    )
                else:
                    result = self._matcher.match(
                        request.request,
                        now=self._clock(),
                    )
            except (
                StoryCandidateRetryableError,
                StoryMatchContextRetryableError,
                StoryConflictError,
            ) as error:
                log_event(
                    LOGGER,
                    "story_matching_retryable",
                    level=logging.WARNING,
                    error=error,
                    event_id=str(request.event_id),
                )
                return StoryWorkResult(
                    request.event_id,
                    StoryWorkStatus.RETRYABLE_FAILURE,
                    None,
                    type(error).__name__,
                    self._clock(),
                )
            except Exception as error:
                log_event(
                    LOGGER,
                    "story_matching_failed",
                    level=logging.ERROR,
                    error=error,
                    event_id=str(request.event_id),
                )
                return StoryWorkResult(
                    request.event_id,
                    StoryWorkStatus.FAILED,
                    None,
                    type(error).__name__,
                    self._clock(),
                )
            if self._processed_store is not None and not getattr(
                self._matcher, "handles_processed_events", False
            ):
                try:
                    if processed_event is None:
                        raise RuntimeError("processed event was not created")
                    self._processed_store.mark_processed(processed_event)
                except Exception as error:
                    return StoryWorkResult(
                        request.event_id,
                        StoryWorkStatus.RETRYABLE_FAILURE,
                        None,
                        type(error).__name__,
                        self._clock(),
                    )
        status = {
            MatchAction.ATTACH: StoryWorkStatus.COMPLETED_ATTACHED,
            MatchAction.CREATE: StoryWorkStatus.COMPLETED_CREATED,
            MatchAction.REVIEW: StoryWorkStatus.COMPLETED_REVIEW,
        }[result.decision.action]
        log_event(
            LOGGER,
            "story_matching_completed",
            event_id=str(request.event_id),
            status=status.value,
            action=result.decision.action.value,
            duration_ms=round((time.monotonic() - started) * 1000),
        )
        return StoryWorkResult(request.event_id, status, result, None, None)
