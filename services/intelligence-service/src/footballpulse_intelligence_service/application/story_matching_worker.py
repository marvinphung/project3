from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from footballpulse_intelligence_service.application.story_matching import (
    StoryMatchContextRetryableError,
    StoryMatchRequest,
    StoryMatchResult,
)
from footballpulse_intelligence_service.domain.errors import StoryConflictError
from footballpulse_intelligence_service.domain.story_candidate_decision import (
    MatchAction,
    StoryCandidateRetryableError,
)


class StoryMatcher(Protocol):
    def match(self, request: StoryMatchRequest, *, now: datetime) -> StoryMatchResult: ...


class StoryWorkStatus(StrEnum):
    COMPLETED_ATTACHED = "COMPLETED_ATTACHED"
    COMPLETED_CREATED = "COMPLETED_CREATED"
    COMPLETED_REVIEW = "COMPLETED_REVIEW"
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
        max_concurrency: int = 1,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if not 1 <= max_concurrency <= 2:
            raise ValueError("Story matching concurrency must be between 1 and 2")
        self._matcher = matcher
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._clock = clock

    async def run(self, request: StoryMatchWorkRequest) -> StoryWorkResult:
        async with self._semaphore:
            try:
                result = await asyncio.to_thread(
                    self._matcher.match,
                    request.request,
                    now=self._clock(),
                )
            except (
                StoryCandidateRetryableError,
                StoryMatchContextRetryableError,
                StoryConflictError,
            ) as error:
                return StoryWorkResult(
                    request.event_id,
                    StoryWorkStatus.RETRYABLE_FAILURE,
                    None,
                    type(error).__name__,
                    self._clock(),
                )
            except Exception as error:
                return StoryWorkResult(
                    request.event_id,
                    StoryWorkStatus.FAILED,
                    None,
                    type(error).__name__,
                    self._clock(),
                )
        status = {
            MatchAction.ATTACH: StoryWorkStatus.COMPLETED_ATTACHED,
            MatchAction.CREATE: StoryWorkStatus.COMPLETED_CREATED,
            MatchAction.REVIEW: StoryWorkStatus.COMPLETED_REVIEW,
        }[result.decision.action]
        return StoryWorkResult(request.event_id, status, result, None, None)
