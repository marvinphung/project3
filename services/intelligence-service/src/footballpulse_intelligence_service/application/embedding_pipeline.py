from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol

from footballpulse_intelligence_service.adapters.embedding_models import (
    MAX_BGE_TOKENS,
    EncodedEmbedding,
)
from footballpulse_intelligence_service.domain.embedding import (
    EmbeddingInput,
    EmbeddingRecord,
    build_embedding_text,
)

INPUT_BUILDER_VERSION = "article-embedding-input-v1"


class EmbeddingAdapter(Protocol):
    model_name: str
    model_version: str

    def encode(
        self,
        texts: list[str],
        *,
        batch_size: int,
        max_tokens: int,
    ) -> list[EncodedEmbedding]: ...


class EmbeddingRepository(Protocol):
    def add_once(self, record: EmbeddingRecord) -> EmbeddingRecord: ...


class EmbeddingPipeline:
    def __init__(
        self,
        *,
        embedder: EmbeddingAdapter,
        repository: EmbeddingRepository,
        clock: Callable[[], datetime],
        batch_size: int = 16,
        max_tokens: int = 512,
        max_items: int = 256,
    ) -> None:
        if batch_size < 1 or not 1 <= max_tokens <= MAX_BGE_TOKENS or max_items < 1:
            raise ValueError("embedding pipeline limits are outside the model contract")
        self._embedder = embedder
        self._repository = repository
        self._clock = clock
        self._batch_size = batch_size
        self._max_tokens = max_tokens
        self._max_items = max_items

    def process_batch(self, items: list[EmbeddingInput]) -> tuple[EmbeddingRecord, ...]:
        if not items or len(items) > self._max_items:
            raise ValueError("embedding work batch size is outside configured limit")
        built_inputs = [build_embedding_text(item) for item in items]
        encoded = self._embedder.encode(
            [item.text for item in built_inputs],
            batch_size=self._batch_size,
            max_tokens=self._max_tokens,
        )
        if len(encoded) != len(built_inputs):
            raise ValueError("embedding adapter result count does not match input")
        now = self._clock()
        records: list[EmbeddingRecord] = []
        for built, output in zip(built_inputs, encoded, strict=True):
            record = EmbeddingRecord.create(
                article_version_id=built.article_version_id,
                input_hash=built.input_hash,
                input_builder_version=INPUT_BUILDER_VERSION,
                model_name=self._embedder.model_name,
                model_version=self._embedder.model_version,
                vector=output.vector,
                token_count=output.token_count,
                embedded_token_count=output.embedded_token_count,
                truncated=output.truncated,
                now=now,
            )
            records.append(self._repository.add_once(record))
        return tuple(records)


class EmbeddingWorkStatus(StrEnum):
    COMPLETED = "COMPLETED"
    EMBEDDING_FAILED = "EMBEDDING_FAILED"


@dataclass(frozen=True, slots=True)
class EmbeddingWorkResult:
    status: EmbeddingWorkStatus
    records: tuple[EmbeddingRecord, ...] | None
    error_type: str | None
    failed_at: datetime | None


class BatchEmbeddingPipeline(Protocol):
    def process_batch(self, items: list[EmbeddingInput]) -> tuple[EmbeddingRecord, ...]: ...


class EmbeddingWorker:
    def __init__(
        self,
        pipeline: BatchEmbeddingPipeline,
        *,
        max_concurrency: int = 1,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if not 1 <= max_concurrency <= 2:
            raise ValueError("embedding model concurrency must be between 1 and 2")
        self._pipeline = pipeline
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._clock = clock

    async def run(self, items: list[EmbeddingInput]) -> EmbeddingWorkResult:
        async with self._semaphore:
            try:
                records = self._pipeline.process_batch(items)
            except Exception as error:
                return EmbeddingWorkResult(
                    EmbeddingWorkStatus.EMBEDDING_FAILED,
                    None,
                    type(error).__name__,
                    self._clock(),
                )
        return EmbeddingWorkResult(EmbeddingWorkStatus.COMPLETED, records, None, None)
