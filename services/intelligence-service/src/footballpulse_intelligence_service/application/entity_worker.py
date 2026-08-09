from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol

from footballpulse_intelligence_service.application.entity_extraction import (
    EntityExtractionResult,
    ExtractionRequest,
)


class ExtractionPipeline(Protocol):
    def process(self, request: ExtractionRequest) -> EntityExtractionResult: ...


class EntityWorkStatus(StrEnum):
    COMPLETED = "COMPLETED"
    ENTITY_EXTRACTION_FAILED = "ENTITY_EXTRACTION_FAILED"


@dataclass(frozen=True, slots=True)
class EntityWorkResult:
    status: EntityWorkStatus
    extraction: EntityExtractionResult | None
    error_type: str | None
    failed_at: datetime | None


class EntityExtractionWorker:
    def __init__(
        self,
        pipeline: ExtractionPipeline,
        *,
        max_concurrency: int = 1,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if not 1 <= max_concurrency <= 2:
            raise ValueError("entity model concurrency must be between 1 and 2")
        self._pipeline = pipeline
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._clock = clock

    async def run(self, request: ExtractionRequest) -> EntityWorkResult:
        async with self._semaphore:
            try:
                result = await asyncio.to_thread(self._pipeline.process, request)
            except Exception as error:
                return EntityWorkResult(
                    EntityWorkStatus.ENTITY_EXTRACTION_FAILED,
                    None,
                    type(error).__name__,
                    self._clock(),
                )
        return EntityWorkResult(EntityWorkStatus.COMPLETED, result, None, None)
