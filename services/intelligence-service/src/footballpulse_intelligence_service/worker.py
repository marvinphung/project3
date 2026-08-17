from __future__ import annotations

import json
import logging
import os
import time
from datetime import UTC, datetime

from pymongo import MongoClient
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from footballpulse_intelligence_service.adapters.embedding_models import (
    BgeEmbeddingAdapter,
    MockEmbeddingAdapter,
)
from footballpulse_intelligence_service.adapters.entity_extractors import (
    CatalogAliasEntityExtractor,
    CatalogEntityRule,
    GlinerEntityExtractor,
)
from footballpulse_intelligence_service.application.article_preprocessing import (
    ArticlePreprocessingWorker,
)
from footballpulse_intelligence_service.application.embedding_pipeline import (
    EmbeddingAdapter,
    EmbeddingPipeline,
)
from footballpulse_intelligence_service.application.entity_catalog import EntityCatalogService
from footballpulse_intelligence_service.application.entity_extraction import (
    EntityExtractionPipeline,
    EntityExtractor,
)
from footballpulse_intelligence_service.persistence.mongo_article_intelligence import (
    MongoArticleIntelligenceRepository,
)
from footballpulse_intelligence_service.persistence.postgres_repository import (
    PostgresEmbeddingRepository,
    PostgresEntityCatalogRepository,
    PostgresUnresolvedMentionRepository,
)

LOGGER = logging.getLogger("footballpulse.intelligence.worker")


def _database_url() -> URL:
    return URL.create(
        "postgresql+psycopg",
        username=os.getenv("FOOTBALLPULSE_POSTGRES_USER", "footballpulse"),
        password=os.getenv("FOOTBALLPULSE_POSTGRES_PASSWORD", "footballpulse_local_only"),
        host=os.getenv("FOOTBALLPULSE_POSTGRES_HOST", "127.0.0.1"),
        port=int(os.getenv("FOOTBALLPULSE_POSTGRES_PORT", "5432")),
        database=os.getenv("FOOTBALLPULSE_POSTGRES_DB", "footballpulse"),
    )


def _log(event: str, **fields: object) -> None:
    LOGGER.info(json.dumps({"event": event, **fields}, default=str, ensure_ascii=False))


def create_worker() -> tuple[ArticlePreprocessingWorker, MongoClient[dict[str, object]]]:
    engine = create_engine(_database_url(), pool_pre_ping=True)
    mongo_client: MongoClient[dict[str, object]] = MongoClient(
        os.getenv(
            "FOOTBALLPULSE_MONGODB_URL",
            "mongodb://127.0.0.1:27017/?replicaSet=rs0",
        )
    )
    database = mongo_client[os.getenv("FOOTBALLPULSE_MONGODB_DB", "footballpulse")]
    source_repository = MongoArticleIntelligenceRepository(database)
    source_repository.ensure_indexes()
    catalog_repository = PostgresEntityCatalogRepository(engine)
    catalog_service = EntityCatalogService(
        catalog_repository,
        clock=lambda: datetime.now(UTC),
    )
    entity_mode = os.getenv("FOOTBALLPULSE_ENTITY_PROVIDER", "catalog").casefold()
    extractor: EntityExtractor
    if entity_mode == "gliner":
        extractor = GlinerEntityExtractor(
            model_id=os.getenv("FOOTBALLPULSE_GLINER_MODEL", "urchade/gliner_small-v2.1")
        )
    elif entity_mode == "catalog":
        extractor = CatalogAliasEntityExtractor(
            rules=tuple(
                CatalogEntityRule(alias.alias, entity.entity_type)
                for alias, entity in catalog_repository.list_resolvable_aliases()
            )
        )
    else:
        raise ValueError("FOOTBALLPULSE_ENTITY_PROVIDER must be catalog or gliner")
    embedding_mode = os.getenv("FOOTBALLPULSE_EMBEDDING_PROVIDER", "mock").casefold()
    embedder: EmbeddingAdapter
    if embedding_mode == "bge":
        embedder = BgeEmbeddingAdapter(
            model_id=os.getenv("FOOTBALLPULSE_BGE_MODEL", "BAAI/bge-small-en-v1.5")
        )
    elif embedding_mode == "mock":
        embedder = MockEmbeddingAdapter()
    else:
        raise ValueError("FOOTBALLPULSE_EMBEDDING_PROVIDER must be mock or bge")
    extraction_pipeline = EntityExtractionPipeline(
        extractor=extractor,
        resolver=catalog_service,
        unresolved_repository=PostgresUnresolvedMentionRepository(engine),
        clock=lambda: datetime.now(UTC),
    )
    embedding_pipeline = EmbeddingPipeline(
        embedder=embedder,
        repository=PostgresEmbeddingRepository(engine),
        clock=lambda: datetime.now(UTC),
    )
    return (
        ArticlePreprocessingWorker(
            source_repository=source_repository,
            extraction_pipeline=extraction_pipeline,
            embedding_pipeline=embedding_pipeline,
            entity_lookup=catalog_repository.get_entity,
            clock=lambda: datetime.now(UTC),
        ),
        mongo_client,
    )


def main() -> None:
    logging.basicConfig(
        level=os.getenv("FOOTBALLPULSE_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    limit = int(os.getenv("FOOTBALLPULSE_INTELLIGENCE_BATCH_SIZE", "50"))
    poll_seconds = float(os.getenv("FOOTBALLPULSE_INTELLIGENCE_POLL_SECONDS", "30"))
    run_once = os.getenv("FOOTBALLPULSE_INTELLIGENCE_RUN_ONCE", "false").casefold() == "true"
    worker, mongo_client = create_worker()
    _log("intelligence_worker_started", batch_size=limit, run_once=run_once)
    try:
        while True:
            report = worker.run_once(limit=limit)
            _log(
                "intelligence_batch_completed",
                claimed=report.claimed,
                completed=report.completed,
                failed=report.failed,
            )
            if run_once:
                break
            time.sleep(poll_seconds)
    finally:
        mongo_client.close()


if __name__ == "__main__":
    main()
