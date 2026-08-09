from __future__ import annotations

import os
import resource
import time
from dataclasses import dataclass
from uuid import uuid4

import pytest
from footballpulse_intelligence_service.adapters.embedding_models import BgeEmbeddingAdapter
from footballpulse_intelligence_service.domain.embedding import (
    EmbeddingInput,
    EmbeddingVector,
    build_embedding_text,
)

pytestmark = pytest.mark.skipif(
    os.getenv("FOOTBALLPULSE_RUN_BGE_ACCEPTANCE") != "1",
    reason="set FOOTBALLPULSE_RUN_BGE_ACCEPTANCE=1 to load the real local model",
)


@dataclass(frozen=True, slots=True)
class Fixture:
    name: str
    title: str
    entities: tuple[str, ...]
    content: str

    def text(self) -> str:
        return build_embedding_text(
            EmbeddingInput(uuid4(), self.title, self.entities, self.content)
        ).text


FIXTURES = (
    Fixture(
        "transfer_report",
        "Arsenal submit offer for Vinicius Junior",
        ("Arsenal", "Real Madrid", "Vinícius Júnior"),
        "Arsenal have submitted a 180 million euro offer to Real Madrid for Vinicius Junior.",
    ),
    Fixture(
        "transfer_update",
        "Real Madrid receive Arsenal bid for Vinicius",
        ("Arsenal", "Real Madrid", "Vinícius Júnior"),
        "Real Madrid are considering Arsenal's formal offer to sign Vinicius Junior.",
    ),
    Fixture(
        "injury_control",
        "Vinicius Junior suffers hamstring injury",
        ("Real Madrid", "Vinícius Júnior"),
        "Vinicius Junior will miss Real Madrid's next game after a hamstring injury.",
    ),
    Fixture(
        "match_control",
        "Arsenal beat Real Madrid in Champions League",
        ("Arsenal", "Real Madrid", "Champions League"),
        "Arsenal defeated Real Madrid 2-1 in their Champions League match.",
    ),
)


def _cosine(left: EmbeddingVector, right: EmbeddingVector) -> float:
    return sum(a * b for a, b in zip(left.values, right.values, strict=True))


def test_real_bge_similarity_latency_and_memory_baseline() -> None:
    adapter = BgeEmbeddingAdapter()
    texts = [fixture.text() for fixture in FIXTURES]
    rss_before_kib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    cold_started = time.perf_counter()
    outputs = adapter.encode(texts, batch_size=16, max_tokens=512)
    cold_seconds = time.perf_counter() - cold_started
    rss_after_kib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    warm_single_started = time.perf_counter()
    adapter.encode([texts[0]], batch_size=16, max_tokens=512)
    warm_single_seconds = time.perf_counter() - warm_single_started

    warm_batch_started = time.perf_counter()
    adapter.encode([texts[0]] * 16, batch_size=16, max_tokens=512)
    warm_batch_seconds = time.perf_counter() - warm_batch_started

    transfer_similarity = _cosine(outputs[0].vector, outputs[1].vector)
    injury_similarity = _cosine(outputs[0].vector, outputs[2].vector)
    match_similarity = _cosine(outputs[0].vector, outputs[3].vector)
    peak_rss_delta_mib = max(0, rss_after_kib - rss_before_kib) / 1024
    print(
        "BGE fixture benchmark: "
        f"transfer={transfer_similarity:.4f}, injury={injury_similarity:.4f}, "
        f"match={match_similarity:.4f}, cold_seconds={cold_seconds:.3f}, "
        f"warm_single_seconds={warm_single_seconds:.3f}, "
        f"warm_batch16_seconds={warm_batch_seconds:.3f}, "
        f"peak_rss_delta_mib={peak_rss_delta_mib:.1f}"
    )

    assert transfer_similarity > injury_similarity
    assert transfer_similarity > match_similarity
    assert all(len(output.vector.values) == 384 for output in outputs)
