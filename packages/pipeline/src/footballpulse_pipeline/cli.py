from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

from confluent_kafka import Consumer
from footballpulse_ai_content_service.persistence.v2_backlog import V2EnrichmentBacklog
from footballpulse_ai_content_service.v2_processor import (
    V2EntityProcessor,
    V2NewsCrawledConsumer,
)
from footballpulse_publisher_service.publisher import V2Publisher
from pymongo import MongoClient
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from footballpulse_pipeline.v2_enrichment_runtime import run_v2_kaggle_enrichment

ROOT = Path(__file__).resolve().parents[4]
REAL_CRAWL_SCRIPT = ROOT / "scripts" / "run-real-crawl.py"


def _load_repo_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _load_real_crawl_script() -> Any:
    spec = importlib.util.spec_from_file_location("footballpulse_real_crawl", REAL_CRAWL_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {REAL_CRAWL_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _mongo_client() -> MongoClient[dict[str, object]]:
    return MongoClient(
        os.getenv(
            "FOOTBALLPULSE_MONGODB_URL",
            "mongodb://127.0.0.1:27117/?directConnection=true",
        ),
        uuidRepresentation="standard",
    )


def _postgres_engine() -> Any:
    if os.getenv("SUPABASE_DB_HOST"):
        url = URL.create(
            "postgresql+psycopg",
            username=os.environ["SUPABASE_DB_USER"],
            password=os.environ["SUPABASE_DB_PASSWORD"],
            host=os.environ["SUPABASE_DB_HOST"],
            port=int(os.environ.get("SUPABASE_DB_PORT", "5432")),
            database=os.environ.get("SUPABASE_DB_NAME", "postgres"),
        )
    else:
        url = URL.create(
            "postgresql+psycopg",
            username=os.getenv("FOOTBALLPULSE_POSTGRES_USER", "footballpulse"),
            password=os.getenv("FOOTBALLPULSE_POSTGRES_PASSWORD", "footballpulse_v2_local"),
            host=os.getenv("FOOTBALLPULSE_POSTGRES_HOST", "127.0.0.1"),
            port=int(os.getenv("FOOTBALLPULSE_POSTGRES_PORT", "15432")),
            database=os.getenv("FOOTBALLPULSE_POSTGRES_DB", "footballpulse_v2"),
        )
    return create_engine(url, pool_pre_ping=True)


_EXTRACTOR: Any = None


def _get_extractor() -> Any:
    global _EXTRACTOR
    if _EXTRACTOR is None:
        try:
            from footballpulse_intelligence_service.adapters.entity_extractors import (
                GlinerEntityExtractor,
            )

            model_name = (
                os.getenv("NER_MODEL_NAME")
                or os.getenv("FOOTBALLPULSE_GLINER_MODEL")
                or "fastino/gliner2-large-v1"
            )
            device = os.getenv("NER_DEVICE") or "cpu"
            _EXTRACTOR = GlinerEntityExtractor(model_id=model_name, device=device)
        except Exception:
            _EXTRACTOR = False
    return _EXTRACTOR


def _extract_entities(text: str) -> list[dict[str, object]]:
    extractor = _get_extractor()
    if extractor:
        try:
            from footballpulse_intelligence_service.domain.extraction import (
                EntityLabel,
                SourceField,
                SpanPrediction,
                deduplicate_predictions,
                split_text,
            )

            min_conf = (
                os.getenv("ENTITY_EXTRACTION_MIN_CONFIDENCE")
                or os.getenv("FOOTBALLPULSE_ENTITY_DETECTION_THRESHOLD")
                or "0.5"
            )
            threshold = float(min_conf)
            chunks = split_text(text, max_words=300, overlap_words=40, max_chunks=64)
            if not chunks:
                return []
            raw_predictions: list[SpanPrediction] = []
            for chunk in chunks:
                spans = extractor.extract(
                    chunk.text,
                    labels=tuple(EntityLabel),
                    threshold=threshold,
                )
                for span in spans:
                    raw_predictions.append(
                        SpanPrediction.create(
                            source_field=SourceField.CONTENT,
                            source_text=text,
                            label=span.label,
                            start=chunk.start + span.start,
                            end=chunk.start + span.end,
                            score=span.score,
                        )
                    )
            deduped = deduplicate_predictions(raw_predictions)
            return [
                {
                    "label": p.label.value.upper(),
                    "text": p.text,
                    "score": p.score,
                    "start": p.start,
                    "end": p.end,
                    "canonical_entity_id": None,
                    "canonical_name": p.text,
                }
                for p in deduped
            ]
        except Exception:
            pass

    entities: list[dict[str, object]] = []
    seen: set[tuple[str, str, int, int]] = set()
    rules = {
        "CLUB": ("FC", "United", "City", "Madrid", "Arsenal", "Liverpool", "Chelsea", "Barcelona"),
        "PERSON": ("said", "manager", "coach", "forward", "midfielder", "defender"),
        "COMPETITION": ("Premier League", "Champions League", "World Cup", "La Liga", "Serie A"),
    }
    words = text.split()
    for index, word in enumerate(words):
        token = word.strip(".,:;!?()[]{}\"'")
        if len(token) < 3:
            continue
        start = text.find(word)
        end = start + len(word)
        if token[:1].isupper():
            label = "PERSON"
            window = " ".join(words[index : index + 3])
            for candidate_label, hints in rules.items():
                if any(hint in window for hint in hints):
                    label = candidate_label
                    break
            key = (label, token, start, end)
            if key in seen:
                continue
            seen.add(key)
            entities.append(
                {
                    "label": label,
                    "text": token,
                    "score": 0.75,
                    "start": start,
                    "end": end,
                    "canonical_entity_id": None,
                    "canonical_name": token,
                }
            )
    return entities


def _run_crawl(arguments: list[str]) -> int:
    module = _load_real_crawl_script()
    original_argv = sys.argv[:]
    try:
        sys.argv = [str(REAL_CRAWL_SCRIPT), *arguments]
        return int(module.main())
    finally:
        sys.argv = original_argv


def _run_process(limit: int) -> int:
    mongo = _mongo_client()
    enriched_status = None
    try:
        database = mongo[os.getenv("FOOTBALLPULSE_MONGODB_DB", "footballpulse_v2")]
        consumer = Consumer(
            {
                "bootstrap.servers": os.getenv(
                    "FOOTBALLPULSE_V2_KAFKA_BOOTSTRAP_SERVERS",
                    "127.0.0.1:19092",
                ),
                "group.id": os.getenv(
                    "FOOTBALLPULSE_V2_PROCESSOR_GROUP",
                    "footballpulse-v2-processor",
                ),
                "enable.auto.commit": False,
                "auto.offset.reset": "earliest",
            }
        )
        processor = V2EntityProcessor(database=database, extractor=_extract_entities)
        worker = V2NewsCrawledConsumer(consumer=consumer, processor=processor)
        processed = 0
        try:
            while processed < limit:
                article_id = worker.run_once(timeout_seconds=2.0)
                if article_id is None:
                    break
                processed += 1
        finally:
            consumer.close()

        # Replay fallback for articles missed by Kafka but still lacking entities.
        if processed < limit:
            backlog = V2EnrichmentBacklog(database)
            remaining = limit - processed
            for document in backlog.iter_unenriched():
                article_id = V2EnrichmentBacklog.article_id(document)
                if database.news_entities.find_one({"_id": article_id}, {"_id": 1}) is not None:
                    continue
                processor.process_article(article_id)
                processed += 1
                remaining -= 1
                if remaining == 0:
                    break
        enriched_status = run_v2_kaggle_enrichment(
            database=database,
            limit=limit,
            root=Path(os.getenv("FOOTBALLPULSE_AI_BATCH_ROOT", ".footballpulse/ai-batches")),
        )
    finally:
        mongo.close()
    status_label = enriched_status.value if enriched_status else "SKIPPED"
    print(
        f"footballpulse_pipeline process completed: processed={processed} "
        f"enrichment_status={status_label}"
    )
    return 0


def _run_publish(limit: int) -> int:
    mongo = _mongo_client()
    engine = _postgres_engine()
    published = 0
    try:
        database = mongo[os.getenv("FOOTBALLPULSE_MONGODB_DB", "footballpulse_v2")]
        publisher = V2Publisher(mongo=database, postgres=engine)
        cursor = database.news_enrichments.find({"validation_status": "VALIDATED"}).sort(
            "processed_at", 1
        )
        for document in cursor:
            article_id = document.get("_id")
            if not isinstance(article_id, UUID):
                continue
            if publisher.publish_article(article_id):
                published += 1
            if published >= limit:
                break
    finally:
        mongo.close()
        engine.dispose()
    print(f"footballpulse_pipeline publish completed: published={published}")
    return 0


def main() -> None:
    _load_repo_env()
    parser = argparse.ArgumentParser(description="FootballPulse v2 local pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    crawl = subparsers.add_parser("crawl")
    crawl.add_argument("--source", action="append")
    crawl.add_argument("--max-articles", type=int, default=10)
    crawl.add_argument("--list-sources", action="store_true")

    process = subparsers.add_parser("process")
    process.add_argument("--limit", type=int, default=20)

    publish = subparsers.add_parser("publish")
    publish.add_argument("--limit", type=int, default=50)

    args = parser.parse_args()
    if args.command == "crawl":
        forwarded: list[str] = []
        if args.list_sources:
            forwarded.append("--list-sources")
        for source_name in args.source or []:
            forwarded.extend(["--source", source_name])
        forwarded.extend(["--max-articles", str(args.max_articles)])
        raise SystemExit(_run_crawl(forwarded))
    if args.command == "process":
        raise SystemExit(_run_process(args.limit))
    raise SystemExit(_run_publish(args.limit))
