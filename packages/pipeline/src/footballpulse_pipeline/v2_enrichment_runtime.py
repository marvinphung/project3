from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4, uuid5

from confluent_kafka import Producer
from pymongo.database import Database

from footballpulse_ai_content_service.batch.artifacts import BatchArtifactStore
from footballpulse_ai_content_service.batch.coordinator import (
    BatchJobRepository,
    EnrichmentPersistenceConflict,
    EnrichmentPersistenceUnavailable,
    GroundedEnrichment,
    KaggleBatchCoordinator,
)
from footballpulse_ai_content_service.batch.domain import AiBatchStatus
from footballpulse_ai_content_service.batch.kaggle_cli import KaggleCli
from footballpulse_ai_content_service.batch.metadata import KAGGLE_PRODUCTION_ACCELERATOR, KaggleMetadataBuilder
from footballpulse_ai_content_service.contracts.enrichment import (
    ArticleEnrichmentInput,
    CanonicalEntityInput,
    EntityType,
)
from footballpulse_ai_content_service.persistence.v2_backlog import V2EnrichmentBacklog
from footballpulse_ai_content_service.v2_enrichment_sink import V2EnrichmentSink

ROOT = Path(__file__).resolve().parents[4]
SOURCE_NAMESPACE = UUID("9f8620af-3c33-49d8-a1c5-0fefadad86f7")
ENTITY_NAMESPACE = UUID("d20a9b22-3d7a-4f45-b19c-814dc1de279b")
MongoDocument = dict[str, Any]


@dataclass
class InMemoryBatchJobRepository(BatchJobRepository):
    status: AiBatchStatus = AiBatchStatus.PREPARING

    def get_status(self, batch_id: UUID) -> AiBatchStatus:
        del batch_id
        return self.status

    def acquire_lease(self, *, owner: str, now: datetime, lease_seconds: int) -> bool:
        del owner, now, lease_seconds
        return True

    def transition(
        self,
        batch_id: UUID,
        *,
        expected: AiBatchStatus,
        target: AiBatchStatus,
        now: datetime,
        success_count: int | None = None,
        error_count: int | None = None,
        error_code: str | None = None,
        error_detail: str | None = None,
    ) -> None:
        del batch_id, now, success_count, error_count, error_code, error_detail
        if self.status is not expected:
            raise EnrichmentPersistenceConflict(
                f"expected batch status {expected.value}, found {self.status.value}"
            )
        self.status = target

    def release_lease(self, *, owner: str) -> None:
        del owner


class V2CoordinatorSink:
    def __init__(self, *, database: Database[MongoDocument], producer: Producer) -> None:
        self._sink = V2EnrichmentSink(database=database, producer=producer)

    def persist(self, outputs: tuple[GroundedEnrichment, ...]) -> None:
        for grounded in outputs:
            source = grounded.validation
            output = grounded.output
            entities: dict[UUID, CanonicalEntityInput] = {}
            for entity in grounded_source_inputs[output.article_version_id].canonical_entities:  # type: ignore[name-defined]
                entities[entity.entity_id] = entity
            claims: list[dict[str, object]] = []
            for claim in source.valid_claims:
                subject = entities.get(claim.subject_entity_id)
                object_entity = entities.get(claim.object_entity_id) if claim.object_entity_id else None
                claims.append(
                    {
                        "subject": subject.canonical_name if subject else str(claim.subject_entity_id),
                        "subject_entity_id": str(claim.subject_entity_id),
                        "predicate": claim.predicate.value,
                        "object": object_entity.canonical_name if object_entity else claim.object_text,
                        "object_entity_id": str(claim.object_entity_id) if claim.object_entity_id else None,
                        "object_value": claim.qualifiers.model_dump(mode="json"),
                        "certainty": claim.certainty.value,
                        "evidence_quote": claim.evidence_quote,
                        "evidence_start": claim.evidence_start,
                        "evidence_end": claim.evidence_end,
                    }
                )
            accepted = self._sink.persist_validated(
                article_id=output.article_version_id,
                output={
                    "validation_status": "VALIDATED",
                    "event_type": output.event_type.value,
                    "summary_en": source.summary_en or output.summary_en,
                    "summary_vi": source.summary_en or output.summary_en,
                    "claims": claims,
                    "model_name": "kaggle-qwen",
                    "model_version": output.model_version,
                    "prompt_version": output.prompt_version,
                },
            )
            if not accepted:
                raise EnrichmentPersistenceUnavailable(
                    f"validated enrichment for {output.article_version_id} was rejected by v2 sink"
                )


grounded_source_inputs: dict[UUID, ArticleEnrichmentInput] = {}


def _entity_type(value: object) -> EntityType | None:
    if not isinstance(value, str):
        return None
    try:
        return EntityType(value)
    except ValueError:
        return None


def _entity_id(label: EntityType, canonical_name: str) -> UUID:
    return uuid5(ENTITY_NAMESPACE, f"{label.value}:{canonical_name.casefold()}")


def _input_hash(payload: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def build_v2_inputs(
    database: Database[MongoDocument],
    *,
    limit: int,
) -> list[ArticleEnrichmentInput]:
    backlog = V2EnrichmentBacklog(database)
    results: list[ArticleEnrichmentInput] = []
    for document in backlog.iter_unenriched():
        article_id = V2EnrichmentBacklog.article_id(document)
        metadata = document.get("metadata")
        content = document.get("content")
        if not isinstance(metadata, dict) or not isinstance(content, str) or not content.strip():
            continue
        entity_document = database.news_entities.find_one({"_id": article_id})
        raw_entities = entity_document.get("entities", []) if isinstance(entity_document, dict) else []
        canonical_entities: list[CanonicalEntityInput] = []
        seen_entity_ids: set[UUID] = set()
        for entity in raw_entities if isinstance(raw_entities, list) else []:
            if not isinstance(entity, dict):
                continue
            label = _entity_type(entity.get("label"))
            canonical_name = entity.get("canonical_name") or entity.get("text")
            if label is None or not isinstance(canonical_name, str) or not canonical_name.strip():
                continue
            entity_uuid = _entity_id(label, canonical_name)
            if entity_uuid in seen_entity_ids:
                continue
            seen_entity_ids.add(entity_uuid)
            canonical_entities.append(
                CanonicalEntityInput(
                    entity_id=entity_uuid,
                    entity_type=label,
                    canonical_name=canonical_name.strip(),
                )
            )
        source_id = uuid5(SOURCE_NAMESPACE, str(metadata.get("domain_name", "unknown")))
        published_at = metadata.get("published_time")
        hash_payload = {
            "article_version_id": article_id,
            "title": metadata.get("title", "Untitled"),
            "cleaned_content": content,
            "published_at": published_at.isoformat() if hasattr(published_at, "isoformat") else None,
            "source_id": source_id,
            "source_reliability_tier": 3,
            "canonical_entities": [entity.model_dump(mode="json") for entity in canonical_entities],
            "unresolved_mentions": [],
        }
        enrichment_input = ArticleEnrichmentInput(
            contract_version="article-enrichment.v1",
            article_version_id=article_id,
            input_hash=_input_hash(hash_payload),
            title=str(metadata.get("title", "Untitled")),
            cleaned_content=content,
            published_at=published_at,
            source_id=source_id,
            source_reliability_tier=3,
            canonical_entities=tuple(canonical_entities),
            unresolved_mentions=(),
        )
        results.append(enrichment_input)
        if len(results) >= limit:
            break
    return results


def run_v2_kaggle_enrichment(
    *,
    database: Database[MongoDocument],
    limit: int,
    root: Path,
) -> AiBatchStatus | None:
    inputs = build_v2_inputs(database, limit=limit)
    grounded_source_inputs.clear()
    grounded_source_inputs.update({item.article_version_id: item for item in inputs})
    if not inputs:
        return None

    now = datetime.now(UTC)
    batch_id = uuid4()
    root.mkdir(parents=True, exist_ok=True)
    artifacts = BatchArtifactStore(root).build(
        batch_id=batch_id,
        inputs=inputs,
        created_at=now,
        model_version=os.environ["FOOTBALLPULSE_KAGGLE_MODEL_SOURCE"],
        prompt_version="article-enrichment-v1",
    )
    kernel_path = root / "kernels" / str(batch_id)
    KaggleMetadataBuilder().prepare_kernel(
        target=kernel_path,
        runner_source=Path(ROOT / "kaggle" / "ai-enrichment" / "footballpulse-ai-enrichment.ipynb"),
        kernel_slug=os.environ["FOOTBALLPULSE_KAGGLE_KERNEL_SLUG"],
        dataset_slug=os.environ["FOOTBALLPULSE_KAGGLE_DATASET_SLUG"],
        model_source=os.environ["FOOTBALLPULSE_KAGGLE_MODEL_SOURCE"],
    )
    producer = Producer(
        {
            "bootstrap.servers": os.getenv(
                "FOOTBALLPULSE_V2_KAFKA_BOOTSTRAP_SERVERS",
                "127.0.0.1:19092",
            )
        }
    )
    try:
        return KaggleBatchCoordinator(
            jobs=InMemoryBatchJobRepository(),
            cli=KaggleCli(),
            sink=V2CoordinatorSink(database=database, producer=producer),
            kernel_slug=os.environ["FOOTBALLPULSE_KAGGLE_KERNEL_SLUG"],
            dataset_slug=os.environ["FOOTBALLPULSE_KAGGLE_DATASET_SLUG"],
            worker_id=f"pipeline-{batch_id}",
            clock=lambda: datetime.now(UTC),
        ).run(
            batch_id=batch_id,
            artifacts=artifacts,
            kernel_path=kernel_path,
            accelerator=os.getenv("FOOTBALLPULSE_KAGGLE_ACCELERATOR", KAGGLE_PRODUCTION_ACCELERATOR),
        )
    finally:
        producer.flush(10)
