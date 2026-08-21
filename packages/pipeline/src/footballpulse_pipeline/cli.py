from __future__ import annotations

import argparse
import importlib.util
import logging
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from confluent_kafka import Consumer
from footballpulse_content_summary_service.summary_generator import SummaryGenerator
from footballpulse_content_summary_service.window_planner import (
    to_utc,
)
from footballpulse_entities_extraction_service.v2_processor import (
    V2EntityProcessor,
    V2NewsCrawledConsumer,
)
from footballpulse_publisher_service.publisher import V2Publisher
from footballpulse_runtime_config import configure_logging, log_event
from pymongo import MongoClient
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parents[4]
REAL_CRAWL_SCRIPT = ROOT / "scripts" / "run-real-crawl.py"
LOGGER = logging.getLogger("footballpulse.pipeline.cli")


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
    if supabase_url := os.getenv("SUPABASE_DATABASE_URL"):
        url = supabase_url
    elif os.getenv("SUPABASE_DB_HOST"):
        url = URL.create(
            "postgresql+psycopg",
            username=os.environ["SUPABASE_DB_USER"],
            password=os.environ["SUPABASE_DB_PASSWORD"],
            host=os.environ["SUPABASE_DB_HOST"],
            port=int(os.environ.get("SUPABASE_DB_PORT", "5432")),
            database=os.environ.get("SUPABASE_DB_NAME", "postgres"),
        )
    else:
        raise RuntimeError("Supabase database configuration is required for publish")
    return create_engine(url, pool_pre_ping=True)


_EXTRACTOR: Any = None


def _get_extractor() -> Any:
    global _EXTRACTOR
    if _EXTRACTOR is None:
        from footballpulse_entities_extraction_service.adapters.entity_extractors import (
            GlinerEntityExtractor,
        )

        model_name = (
            os.getenv("NER_MODEL_NAME")
            or os.getenv("FOOTBALLPULSE_GLINER_MODEL")
            or "fastino/gliner2-large-v1"
        )
        device = os.getenv("NER_DEVICE") or "cpu"
        _EXTRACTOR = GlinerEntityExtractor(model_id=model_name, device=device)
    return _EXTRACTOR


def _extract_entities(text: str) -> list[dict[str, object]]:
    extractor = _get_extractor()
    if extractor:
        try:
            from footballpulse_entities_extraction_service.domain.extraction import (
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
        except Exception as exc:
            raise RuntimeError("entity extraction failed; GLiNER2 model runtime is required") from exc

    raise RuntimeError("entity extraction failed; GLiNER2 extractor is unavailable")


def _run_crawl(arguments: list[str]) -> int:
    module = _load_real_crawl_script()
    original_argv = sys.argv[:]
    try:
        sys.argv = [str(REAL_CRAWL_SCRIPT), *arguments]
        return int(module.main())
    finally:
        sys.argv = original_argv


def _run_process(limit: int) -> int:
    started = time.monotonic()
    log_event(LOGGER, "pipeline_process_started", limit=limit)
    mongo = _mongo_client()
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
                    "footballpulse-v2-entities-extraction",
                ),
                "enable.auto.commit": False,
                "auto.offset.reset": "earliest",
            }
        )
        processor = V2EntityProcessor(database=database, extractor=_extract_entities)
        worker = V2NewsCrawledConsumer(consumer=consumer, processor=processor)
        processed = 0
        kafka_processed = 0
        fallback_processed = 0
        try:
            log_event(LOGGER, "pipeline_process_kafka_drain_started", limit=limit)
            while processed < limit:
                article_id = worker.run_once(timeout_seconds=2.0)
                if article_id is None:
                    log_event(
                        LOGGER,
                        "pipeline_process_kafka_drain_empty",
                        processed=processed,
                        timeout_seconds=2.0,
                    )
                    break
                processed += 1
                kafka_processed += 1
                log_event(
                    LOGGER,
                    "pipeline_process_kafka_progress",
                    processed=processed,
                    limit=limit,
                    article_id=str(article_id),
                )
        finally:
            consumer.close()

        # Replay fallback for articles missed by Kafka but still lacking entities.
        if processed < limit:
            remaining = limit - processed
            log_event(LOGGER, "pipeline_process_backlog_started", remaining=remaining)
            pipeline: list[dict[str, object]] = [
                {
                    "$lookup": {
                        "from": "news_entities",
                        "localField": "_id",
                        "foreignField": "_id",
                        "as": "entity_match",
                    }
                },
                {"$match": {"entity_match": {"$size": 0}}},
                {"$sort": {"crawl_date": -1, "_id": 1}},
                {"$limit": remaining},
            ]
            for document in database.news_metadata.aggregate(pipeline):
                article_id = document.get("_id")
                if not isinstance(article_id, UUID):
                    log_event(
                        LOGGER,
                        "pipeline_process_backlog_invalid_article_id",
                        article_id=str(article_id),
                        level=logging.WARNING,
                    )
                    continue
                try:
                    processor.process_article(article_id)
                except ValueError as exc:
                    if "article content not found" not in str(exc):
                        raise
                    now = datetime.now(UTC)
                    database.news_entities.replace_one(
                        {"_id": article_id},
                        {
                            "_id": article_id,
                            "entities": [],
                            "model_name": os.getenv("NER_MODEL_NAME", "gliner2"),
                            "model_version": os.getenv(
                                "FOOTBALLPULSE_GLINER_MODEL",
                                "fastino/gliner2-large-v1",
                            ),
                            "processed_at": now,
                            "error": "article_content_not_found",
                        },
                        upsert=True,
                    )
                    log_event(
                        LOGGER,
                        "pipeline_process_backlog_marked_missing_content",
                        article_id=str(article_id),
                        level=logging.WARNING,
                    )
                processed += 1
                fallback_processed += 1
                remaining -= 1
                log_event(
                    LOGGER,
                    "pipeline_process_backlog_progress",
                    processed=processed,
                    limit=limit,
                    remaining=remaining,
                    article_id=str(article_id),
                )
                if remaining == 0:
                    break
            log_event(
                LOGGER,
                "pipeline_process_backlog_completed",
                processed=fallback_processed,
            )
    finally:
        mongo.close()
    log_event(
        LOGGER,
        "pipeline_process_completed",
        processed=processed,
        kafka_processed=kafka_processed,
        fallback_processed=fallback_processed,
        duration_ms=round((time.monotonic() - started) * 1000),
    )
    print(f"footballpulse_pipeline entities extraction completed: processed={processed}")
    return 0


def _run_summary(
    window_start_str: str | None,
    window_end_str: str | None,
    force: bool = False,
    backfill_days: int = 7,
) -> int:
    mongo = _mongo_client()
    try:
        database = mongo[os.getenv("FOOTBALLPULSE_MONGODB_DB", "footballpulse_v2")]
        generator = SummaryGenerator(database=database)
        if window_start_str and window_end_str:
            window_start = to_utc(datetime.fromisoformat(window_start_str.replace("Z", "+00:00")))
            window_end = to_utc(datetime.fromisoformat(window_end_str.replace("Z", "+00:00")))
            summaries = generator.process_window(
                window_start=window_start,
                window_end=window_end,
                force_recompute=force,
            )
            print(
                f"footballpulse_pipeline summary completed: "
                f"window=[{window_start.isoformat()} -> {window_end.isoformat()}], "
                f"generated={len(summaries)}"
            )
        else:
            summaries = generator.process_recent_windows(
                days=backfill_days,
                force_recompute=force,
            )
            print(
                f"footballpulse_pipeline summary completed: "
                f"backfill_days={backfill_days}, "
                f"processed={len(summaries)}"
            )
    finally:
        mongo.close()
    return 0


def _run_publish(limit: int) -> int:
    mongo = _mongo_client()
    engine = _postgres_engine()
    published = 0
    backfilled = 0
    try:
        database = mongo[os.getenv("FOOTBALLPULSE_MONGODB_DB", "footballpulse_v2")]
        publisher = V2Publisher(mongo=database, postgres=engine)
        published = publisher.publish_pending(limit=limit)
        backfilled = publisher.backfill_source_articles()
    finally:
        mongo.close()
        engine.dispose()
    print(f"footballpulse_pipeline publish completed: published={published}, backfilled={backfilled}")
    return 0


def main() -> None:
    _load_repo_env()
    configure_logging(
        service="footballpulse-pipeline",
        level=os.getenv("FOOTBALLPULSE_LOG_LEVEL", "INFO"),
        force=True,
    )
    parser = argparse.ArgumentParser(description="FootballPulse v2 local pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    crawl = subparsers.add_parser("crawl")
    crawl.add_argument("--source", action="append")
    crawl.add_argument("--max-articles", type=int, default=20)
    crawl.add_argument(
        "--step",
        choices=["all", "1", "2", "discovery", "content"],
        default="all",
    )
    crawl.add_argument("--concurrency", type=int, default=6)
    crawl.add_argument("--max-age-days", type=int, default=30)
    crawl.add_argument("--list-sources", action="store_true")

    process = subparsers.add_parser("process")
    process.add_argument("--limit", type=int, default=20)

    summary = subparsers.add_parser("summary")
    summary.add_argument("--window-start", type=str, default=None)
    summary.add_argument("--window-end", type=str, default=None)
    summary.add_argument("--force", action="store_true", default=False)
    summary.add_argument("--backfill-days", type=int, default=7)

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
        if args.step != "all":
            forwarded.extend(["--step", args.step])
        if args.concurrency != 6:
            forwarded.extend(["--concurrency", str(args.concurrency)])
        if args.max_age_days != 30:
            forwarded.extend(["--max-age-days", str(args.max_age_days)])
        raise SystemExit(_run_crawl(forwarded))
    if args.command == "process":
        raise SystemExit(_run_process(args.limit))
    if args.command == "summary":
        raise SystemExit(_run_summary(args.window_start, args.window_end, args.force, args.backfill_days))
    raise SystemExit(_run_publish(args.limit))
