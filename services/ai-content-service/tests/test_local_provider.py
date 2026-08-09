from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from footballpulse_ai_content_service.contracts.enrichment import ArticleEnrichmentInput
from footballpulse_ai_content_service.providers.local import (
    LocalGenerationTimeout,
    LocalModelManager,
    LocalModelSettings,
    LocalQwenProvider,
)

ARTICLE_ID = UUID("00000000-0000-4000-8000-000000000101")
SOURCE_ID = UUID("00000000-0000-4000-8000-000000000201")
INPUT_HASH = "a" * 64


def article_input(*, content: str = "Arsenal submitted an offer.") -> ArticleEnrichmentInput:
    return ArticleEnrichmentInput.model_validate(
        {
            "contract_version": "article-enrichment.v1",
            "article_version_id": str(ARTICLE_ID),
            "input_hash": INPUT_HASH,
            "title": "Arsenal submit offer",
            "cleaned_content": content,
            "published_at": "2026-08-10T08:00:00Z",
            "source_id": str(SOURCE_ID),
            "source_reliability_tier": 1,
            "canonical_entities": [],
            "unresolved_mentions": [],
        }
    )


def valid_output(
    *,
    summary: str = "Arsenal submitted an offer.",
    article_id: UUID = ARTICLE_ID,
) -> str:
    return json.dumps(
        {
            "contract_version": "article-enrichment.v1",
            "article_version_id": str(article_id),
            "input_hash": INPUT_HASH,
            "event_type": "TRANSFER",
            "summary_en": summary,
            "claims": [],
            "model_version": "ignored-by-provider",
            "prompt_version": "article-enrichment-v1",
        }
    )


class FakeRuntime:
    def __init__(self, responses: list[str | Exception]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def complete(
        self,
        *,
        messages: list[dict[str, str]],
        response_schema: dict[str, Any],
        max_tokens: int,
        timeout_seconds: float,
    ) -> str:
        self.calls.append(
            {
                "messages": messages,
                "response_schema": response_schema,
                "max_tokens": max_tokens,
                "timeout_seconds": timeout_seconds,
            }
        )
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def close(self) -> None:
        self.closed = True


class FakeFactory:
    def __init__(self, runtime: FakeRuntime) -> None:
        self.runtime = runtime
        self.calls = 0

    def load(self, settings: LocalModelSettings) -> FakeRuntime:
        self.calls += 1
        return self.runtime


def settings(model_path: Path, *, checksum: str | None = None) -> LocalModelSettings:
    return LocalModelSettings(
        model_path=model_path,
        model_sha256=checksum,
        model_version="Qwen3-4B-Instruct-GGUF-Q4_K_M",
        n_ctx=8_192,
        n_threads=8,
    )


def test_settings_validate_gguf_path_size_and_optional_checksum(tmp_path: Path) -> None:
    model = tmp_path / "qwen3-4b-q4_k_m.gguf"
    model.write_bytes(b"fake-gguf-model")
    digest = hashlib.sha256(model.read_bytes()).hexdigest()

    validated = settings(model, checksum=digest).validate_model_file(min_size_bytes=1)

    assert validated == model.resolve()
    with pytest.raises(ValueError, match="checksum"):
        settings(model, checksum="0" * 64).validate_model_file(min_size_bytes=1)


def test_provider_lazy_loads_once_and_unloads_after_idle(tmp_path: Path) -> None:
    model = tmp_path / "model.gguf"
    model.write_bytes(b"model")
    runtime = FakeRuntime([valid_output()])
    factory = FakeFactory(runtime)
    now = [0.0]
    manager = LocalModelManager(
        settings(model),
        factory=factory,
        monotonic=lambda: now[0],
        min_model_size_bytes=1,
        idle_timeout_seconds=900,
    )
    provider = LocalQwenProvider(manager=manager, monotonic=lambda: now[0])

    assert provider.enrich((article_input(),))[0].status == "SUCCESS"
    assert factory.calls == 1
    now[0] = 899
    assert manager.unload_if_idle() is False
    now[0] = 900
    assert manager.unload_if_idle() is True
    assert runtime.closed is True


def test_provider_chunks_content_and_repairs_invalid_json_once(tmp_path: Path) -> None:
    model = tmp_path / "model.gguf"
    model.write_bytes(b"model")
    runtime = FakeRuntime(
        ["not-json", valid_output(summary="First chunk."), valid_output(summary="Second chunk.")]
    )
    manager = LocalModelManager(
        settings(model),
        factory=FakeFactory(runtime),
        min_model_size_bytes=1,
    )
    provider = LocalQwenProvider(
        manager=manager,
        max_chunk_words=4,
        overlap_words=1,
    )

    record = provider.enrich((article_input(content="zero one two three four five"),))[0]

    assert record.status == "SUCCESS"
    assert record.result.summary_en == "First chunk. Second chunk."
    assert len(runtime.calls) == 3
    assert all(call["max_tokens"] == 2_500 for call in runtime.calls)


def test_article_timeout_isolated_as_error_and_batch_continues(tmp_path: Path) -> None:
    model = tmp_path / "model.gguf"
    model.write_bytes(b"model")
    runtime = FakeRuntime(
        [LocalGenerationTimeout("deadline"), valid_output(article_id=UUID(int=2))]
    )
    manager = LocalModelManager(
        settings(model),
        factory=FakeFactory(runtime),
        min_model_size_bytes=1,
    )
    provider = LocalQwenProvider(manager=manager)
    first = article_input()
    second = first.model_copy(update={"article_version_id": UUID(int=2)})

    records = provider.enrich((first, second))

    assert records[0].status == "ERROR"
    assert records[0].error_code == "LOCAL_TIMEOUT"
    assert records[1].status == "SUCCESS"


def test_local_batch_is_bounded_to_twenty_articles(tmp_path: Path) -> None:
    model = tmp_path / "model.gguf"
    model.write_bytes(b"model")
    manager = LocalModelManager(
        settings(model),
        factory=FakeFactory(FakeRuntime([])),
        min_model_size_bytes=1,
    )
    provider = LocalQwenProvider(manager=manager)
    sources = tuple(
        article_input().model_copy(update={"article_version_id": UUID(int=index + 1)})
        for index in range(21)
    )

    with pytest.raises(ValueError, match="20"):
        provider.enrich(sources)
