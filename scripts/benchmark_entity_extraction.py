from __future__ import annotations

import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.extend(
    [
        str(ROOT / "packages/runtime-config/src"),
        str(ROOT / "packages/shared/src"),
        str(ROOT / "services/intelligence-service/src"),
    ]
)

from footballpulse_intelligence_service.adapters.entity_extractors import (
    GlinerEntityExtractor,
)
from footballpulse_intelligence_service.domain.extraction import EntityLabel

BENCHMARK_INPUTS = [
    (
        "Manchester United manager Erik ten Hag praised Bruno Fernandes and Marcus Rashford "
        "after the FA Cup final at Wembley."
    ),
    (
        "Arsenal manager Mikel Arteta praised Bukayo Saka after Arsenal beat Liverpool "
        "in the Premier League."
    ),
    (
        "Pep Guardiola said Erling Haaland will start for Manchester City "
        "in the Champions League against Real Madrid."
    ),
    "Manchester United played the FA Cup final at Wembley Stadium in London.",
    "The weather was warm and the stadium opened at noon without incident.",
    (
        "Real Madrid forward Vinicius Junior scored twice against Borussia Dortmund "
        "in the Champions League final."
    ),
    (
        "Bayern Munich striker Harry Kane scored a hat-trick against Bayer Leverkusen "
        "in the Bundesliga clash."
    ),
    (
        "Barcelona manager Hansi Flick expressed satisfaction with Lamine Yamal "
        "and Robert Lewandowski in La Liga."
    ),
    (
        "Chelsea head coach Enzo Maresca discussed Cole Palmer after their victory "
        "against Newcastle United."
    ),
    "Inter Milan defeated Juventus in Serie A thanks to a late goal from Lautaro Martinez.",
    (
        "Aston Villa qualified for the Champions League under manager Unai Emery "
        "following their Premier League campaign."
    ),
    "Tottenham Hotspur captain Son Heung-min scored in the London derby against West Ham United.",
    (
        "Atletico Madrid coach Diego Simeone praised Antoine Griezmann "
        "and Julian Alvarez after the match."
    ),
    (
        "Paris Saint-Germain winger Ousmane Dembele played a crucial role "
        "in Ligue 1 under Luis Enrique."
    ),
    (
        "Liverpool defender Virgil van Dijk spoke to reporters after Arne Slot "
        "secured his first Premier League win."
    ),
]


def run_benchmark(num_runs: int = 3) -> None:
    model_name = os.getenv("NER_MODEL_NAME", "fastino/gliner2-large-v1")
    device = os.getenv("NER_DEVICE", "cpu")
    threshold = float(os.getenv("ENTITY_EXTRACTION_MIN_CONFIDENCE", "0.5"))

    print("=" * 60)
    print(f"NER Benchmark: Model={model_name} Device={device}")
    print("=" * 60)

    start_load = time.monotonic()
    extractor = GlinerEntityExtractor(model_id=model_name, device=device)
    _ = extractor.extract("Warmup text", labels=tuple(EntityLabel), threshold=threshold)
    load_duration = time.monotonic() - start_load
    print(f"Model Load Time: {load_duration:.3f}s")

    test_articles = BENCHMARK_INPUTS * num_runs
    total_articles = len(test_articles)

    latencies: list[float] = []
    text_lengths: list[int] = []
    entity_counts: list[int] = []

    print(f"Running inference on {total_articles} articles...")
    for _idx, text in enumerate(test_articles, 1):
        text_lengths.append(len(text))
        start_inf = time.monotonic()
        spans = extractor.extract(text, labels=tuple(EntityLabel), threshold=threshold)
        dur = (time.monotonic() - start_inf) * 1000.0
        latencies.append(dur)
        entity_counts.append(len(spans))

    sorted_latencies = sorted(latencies)
    avg_latency = statistics.mean(latencies)
    p50_latency = statistics.median(latencies)
    p90_latency = sorted_latencies[int(0.90 * len(sorted_latencies))]
    p95_latency = sorted_latencies[int(0.95 * len(sorted_latencies))]
    p99_idx = min(int(0.99 * len(sorted_latencies)), len(sorted_latencies) - 1)
    p99_latency = sorted_latencies[p99_idx]
    avg_entities = statistics.mean(entity_counts)
    avg_text_len = statistics.mean(text_lengths)

    print("\n" + "=" * 50)
    print("BENCHMARK RESULTS")
    print("=" * 50)
    print(f"articles: {total_articles}")
    print(f"avg text length: {avg_text_len:.1f} chars")
    print(f"model load time: {load_duration:.3f}s")
    print(f"avg latency: {avg_latency:.2f} ms/article")
    print(f"p50 latency: {p50_latency:.2f} ms/article")
    print(f"p90 latency: {p90_latency:.2f} ms/article")
    print(f"p95 latency: {p95_latency:.2f} ms/article")
    print(f"p99 latency: {p99_latency:.2f} ms/article")
    print(f"entities/article: {avg_entities:.2f}")
    print(f"throughput: {total_articles / (sum(latencies) / 1000.0):.2f} articles/sec")
    print("=" * 50)


if __name__ == "__main__":
    run_benchmark(num_runs=3)
