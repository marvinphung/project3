from __future__ import annotations

import gc
import hashlib
import json
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Lock, Timer
from time import monotonic
from typing import Any, Protocol

from pydantic import ValidationError

from footballpulse_ai_content_service.contracts.batch import (
    BatchRecord,
    FailedBatchRecord,
    SuccessfulBatchRecord,
)
from footballpulse_ai_content_service.contracts.enrichment import (
    ArticleEnrichmentInput,
    ArticleEnrichmentOutput,
)
from footballpulse_ai_content_service.processing.claims import (
    ContentChunk,
    globalize_claim,
    split_content,
)
from footballpulse_ai_content_service.providers.base import ProviderName

PROMPT_VERSION = "article-enrichment-v1"


class LocalGenerationTimeout(TimeoutError):
    pass


class LocalRuntimeFatalError(RuntimeError):
    pass


class LocalProviderUnavailable(RuntimeError):
    pass


class LocalChatRuntime(Protocol):
    def complete(
        self,
        *,
        messages: list[dict[str, str]],
        response_schema: dict[str, Any],
        max_tokens: int,
        timeout_seconds: float,
    ) -> str: ...

    def close(self) -> None: ...


class LocalRuntimeFactory(Protocol):
    def load(self, settings: LocalModelSettings) -> LocalChatRuntime: ...


@dataclass(frozen=True, slots=True)
class LocalModelSettings:
    model_path: Path
    model_version: str
    n_ctx: int = 8_192
    n_threads: int = 8
    model_sha256: str | None = None

    def __post_init__(self) -> None:
        if not self.model_version.strip():
            raise ValueError("local model_version cannot be empty")
        if self.n_ctx < 2_048 or self.n_threads < 1:
            raise ValueError("local model context and thread count are invalid")
        if (
            self.model_sha256 is not None
            and re.fullmatch(r"[a-f0-9]{64}", self.model_sha256) is None
        ):
            raise ValueError("local model checksum must be lowercase SHA-256")

    def validate_model_file(
        self,
        *,
        min_size_bytes: int = 1024 * 1024,
        max_size_bytes: int = 16 * 1024 * 1024 * 1024,
    ) -> Path:
        path = self.model_path.expanduser().resolve()
        if path.suffix.casefold() != ".gguf" or not path.is_file():
            raise ValueError("local model path must be an existing GGUF file")
        size = path.stat().st_size
        if not min_size_bytes <= size <= max_size_bytes:
            raise ValueError("local GGUF size is outside configured bounds")
        if self.model_sha256 is not None:
            digest = hashlib.sha256()
            with path.open("rb") as model_file:
                for block in iter(lambda: model_file.read(1024 * 1024), b""):
                    digest.update(block)
            if digest.hexdigest() != self.model_sha256:
                raise ValueError("local model checksum does not match")
        return path


class LocalModelManager:
    def __init__(
        self,
        settings: LocalModelSettings,
        *,
        factory: LocalRuntimeFactory,
        monotonic: Callable[[], float] = monotonic,
        idle_timeout_seconds: int = 900,
        min_model_size_bytes: int = 1024 * 1024,
        max_model_size_bytes: int = 16 * 1024 * 1024 * 1024,
    ) -> None:
        if idle_timeout_seconds <= 0:
            raise ValueError("idle timeout must be positive")
        self.settings = settings
        self._factory = factory
        self._monotonic = monotonic
        self._idle_timeout_seconds = idle_timeout_seconds
        self._min_model_size_bytes = min_model_size_bytes
        self._max_model_size_bytes = max_model_size_bytes
        self._runtime: LocalChatRuntime | None = None
        self._last_used_at: float | None = None
        self._idle_timer: Timer | None = None
        self._lock = Lock()

    def acquire(self) -> LocalChatRuntime:
        with self._lock:
            self._unload_if_expired_locked()
            if self._runtime is None:
                self.settings.validate_model_file(
                    min_size_bytes=self._min_model_size_bytes,
                    max_size_bytes=self._max_model_size_bytes,
                )
                try:
                    self._runtime = self._factory.load(self.settings)
                except Exception as error:
                    raise LocalProviderUnavailable("local GGUF model failed to load") from error
            self._last_used_at = self._monotonic()
            self._schedule_unload_locked()
            return self._runtime

    def mark_used(self) -> None:
        with self._lock:
            if self._runtime is not None:
                self._last_used_at = self._monotonic()
                self._schedule_unload_locked()

    def unload_if_idle(self) -> bool:
        with self._lock:
            unloaded = self._unload_if_expired_locked()
            if not unloaded and self._runtime is not None and self._last_used_at is not None:
                elapsed = self._monotonic() - self._last_used_at
                self._schedule_unload_locked(max(0.1, self._idle_timeout_seconds - elapsed))
            return unloaded

    def _unload_if_expired_locked(self) -> bool:
        if self._runtime is None or self._last_used_at is None:
            return False
        if self._monotonic() - self._last_used_at < self._idle_timeout_seconds:
            return False
        self._runtime.close()
        self._runtime = None
        self._last_used_at = None
        if self._idle_timer is not None:
            self._idle_timer.cancel()
            self._idle_timer = None
        gc.collect()
        return True

    def _schedule_unload_locked(self, delay_seconds: float | None = None) -> None:
        if self._idle_timer is not None:
            self._idle_timer.cancel()
        timer = Timer(delay_seconds or self._idle_timeout_seconds, self.unload_if_idle)
        timer.daemon = True
        timer.start()
        self._idle_timer = timer


class LocalQwenProvider:
    name = ProviderName.LOCAL

    def __init__(
        self,
        *,
        manager: LocalModelManager,
        monotonic: Callable[[], float] = monotonic,
        article_timeout_seconds: int = 300,
        max_batch_size: int = 20,
        max_chunk_words: int = 1_200,
        overlap_words: int = 150,
        max_output_tokens: int = 2_500,
    ) -> None:
        if article_timeout_seconds <= 0 or max_batch_size < 1 or max_output_tokens < 1:
            raise ValueError("local provider budgets must be positive")
        self._manager = manager
        self._monotonic = monotonic
        self._article_timeout_seconds = article_timeout_seconds
        self._max_batch_size = max_batch_size
        self._max_chunk_words = max_chunk_words
        self._overlap_words = overlap_words
        self._max_output_tokens = max_output_tokens
        self._inference_lock = Lock()

    def enrich(self, inputs: tuple[ArticleEnrichmentInput, ...]) -> tuple[BatchRecord, ...]:
        if len(inputs) > self._max_batch_size:
            raise ValueError(f"local batch cannot exceed {self._max_batch_size} articles")
        if not inputs:
            return ()
        with self._inference_lock:
            runtime = self._manager.acquire()
            records = tuple(self._enrich_one(runtime, source) for source in inputs)
            self._manager.mark_used()
            return records

    def _enrich_one(
        self,
        runtime: LocalChatRuntime,
        source: ArticleEnrichmentInput,
    ) -> BatchRecord:
        deadline = self._monotonic() + self._article_timeout_seconds
        try:
            chunks = split_content(
                source.cleaned_content,
                max_words=self._max_chunk_words,
                overlap_words=self._overlap_words,
            )
            outputs = [self._generate_chunk(runtime, source, chunk, deadline) for chunk in chunks]
            if not outputs:
                raise ValueError("article content has no model chunks")
            global_claims = tuple(
                globalize_claim(chunk, claim)
                for chunk, output in zip(chunks, outputs, strict=True)
                for claim in output.claims
            )
            event_counts = Counter(output.event_type for output in outputs)
            event_type = max(event_counts, key=lambda value: event_counts[value])
            summary = " ".join(dict.fromkeys(output.summary_en for output in outputs))
            combined = ArticleEnrichmentOutput(
                contract_version="article-enrichment.v1",
                article_version_id=source.article_version_id,
                input_hash=source.input_hash,
                event_type=event_type,
                summary_en=summary,
                claims=global_claims,
                model_version=self._manager.settings.model_version,
                prompt_version=PROMPT_VERSION,
            )
            return SuccessfulBatchRecord(
                article_version_id=source.article_version_id,
                status="SUCCESS",
                result=combined,
            )
        except LocalGenerationTimeout as error:
            return self._error(source, "LOCAL_TIMEOUT", error)
        except (ValidationError, ValueError, json.JSONDecodeError) as error:
            return self._error(source, "LOCAL_OUTPUT_INVALID", error)

    def _generate_chunk(
        self,
        runtime: LocalChatRuntime,
        source: ArticleEnrichmentInput,
        chunk: ContentChunk,
        deadline: float,
    ) -> ArticleEnrichmentOutput:
        chunk_mentions = tuple(
            mention.model_copy(
                update={
                    "start": mention.start - chunk.start,
                    "end": mention.end - chunk.start,
                }
            )
            for mention in source.unresolved_mentions
            if mention.start >= chunk.start and mention.end <= chunk.end
        )
        chunk_source = source.model_copy(
            update={
                "cleaned_content": chunk.text,
                "unresolved_mentions": chunk_mentions,
            }
        )
        messages = self._messages(chunk_source)
        raw = runtime.complete(
            messages=messages,
            response_schema=ArticleEnrichmentOutput.model_json_schema(),
            max_tokens=self._max_output_tokens,
            timeout_seconds=self._remaining(deadline),
        )
        try:
            output = ArticleEnrichmentOutput.model_validate_json(raw)
        except ValidationError as first_error:
            repair_messages = messages + [
                {"role": "assistant", "content": raw[:4_000]},
                {
                    "role": "user",
                    "content": "Return one corrected JSON object only. Error: "
                    + str(first_error)[:2_000],
                },
            ]
            repaired = runtime.complete(
                messages=repair_messages,
                response_schema=ArticleEnrichmentOutput.model_json_schema(),
                max_tokens=self._max_output_tokens,
                timeout_seconds=self._remaining(deadline),
            )
            output = ArticleEnrichmentOutput.model_validate_json(repaired)
        if (
            output.article_version_id != source.article_version_id
            or output.input_hash != source.input_hash
        ):
            raise ValueError("local output identity does not match article input")
        return output

    def _remaining(self, deadline: float) -> float:
        remaining = deadline - self._monotonic()
        if remaining <= 0:
            raise LocalGenerationTimeout("local article inference deadline exceeded")
        return remaining

    @staticmethod
    def _messages(source: ArticleEnrichmentInput) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "Extract only grounded football facts. Return strict JSON matching "
                    "the supplied schema. Never invent entities, amounts, dates, scores, "
                    "certainty, or evidence."
                ),
            },
            {
                "role": "user",
                "content": source.model_dump_json(),
            },
        ]

    @staticmethod
    def _error(
        source: ArticleEnrichmentInput,
        code: str,
        error: Exception,
    ) -> FailedBatchRecord:
        return FailedBatchRecord(
            article_version_id=source.article_version_id,
            input_hash=source.input_hash,
            status="ERROR",
            error_code=code,
            error=" ".join(str(error).split())[:500] or "local inference failed",
        )
