from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from footballpulse_intelligence_service.application.article_preprocessing import (
    ArticlePreprocessingWorker,
    SourceArticle,
)
from footballpulse_intelligence_service.application.entity_extraction import (
    EntityExtractionResult,
    ResolutionStatus,
    ResolvedMention,
)
from footballpulse_intelligence_service.domain.embedding import EmbeddingInput
from footballpulse_intelligence_service.domain.entity import Entity, EntityType
from footballpulse_intelligence_service.domain.extraction import (
    EntityLabel,
    SourceField,
    SpanPrediction,
)

ARTICLE_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c3101")
ENTITY_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c8102")
NOW = datetime(2026, 8, 17, 12, tzinfo=UTC)


class SourceRepository:
    def __init__(self) -> None:
        self.saved = []

    def claim_pending(self, *, limit: int):
        assert limit == 10
        return [SourceArticle(ARTICLE_ID, "Arsenal update", "Arsenal submitted an offer.")]

    def save_result(self, result):
        self.saved.append(result)


class ExtractionPipeline:
    def process(self, request):
        prediction = SpanPrediction.create(
            source_field=SourceField.CONTENT,
            source_text=request.cleaned_content,
            label=EntityLabel.CLUB,
            start=0,
            end=7,
            score=1.0,
        )
        return EntityExtractionResult(
            request.article_version_id,
            (ResolvedMention(prediction, ResolutionStatus.RESOLVED, ENTITY_ID),),
            "catalog-alias",
            "catalog-v1",
            0.5,
            0.75,
        )


class EmbeddingPipeline:
    def __init__(self) -> None:
        self.items: list[EmbeddingInput] = []

    def process_batch(self, items):
        self.items.extend(items)
        return (type("Embedding", (), {"id": UUID(int=3), "input_hash": "a" * 64})(),)


def test_worker_persists_grounded_entities_and_embedding_reference() -> None:
    source = SourceRepository()
    embedding = EmbeddingPipeline()
    arsenal = Entity.create(
        entity_id=ENTITY_ID,
        entity_type=EntityType.CLUB,
        canonical_name="Arsenal",
        slug="arsenal",
        now=NOW,
    )
    worker = ArticlePreprocessingWorker(
        source_repository=source,
        extraction_pipeline=ExtractionPipeline(),
        embedding_pipeline=embedding,
        entity_lookup=lambda entity_id: arsenal if entity_id == ENTITY_ID else None,
        clock=lambda: NOW,
    )

    report = worker.run_once(limit=10)

    assert report.completed == 1
    assert report.failed == 0
    assert embedding.items[0].canonical_entities == ("Arsenal",)
    assert source.saved[0].status == "COMPLETED"
    assert source.saved[0].canonical_entities[0].canonical_name == "Arsenal"
    assert source.saved[0].embedding_id == UUID(int=3)


def test_worker_records_bounded_failure_without_stopping_batch() -> None:
    source = SourceRepository()

    class BrokenExtraction:
        def process(self, request):
            raise RuntimeError("model exploded with secret details")

    worker = ArticlePreprocessingWorker(
        source_repository=source,
        extraction_pipeline=BrokenExtraction(),
        embedding_pipeline=EmbeddingPipeline(),
        entity_lookup=lambda entity_id: None,
        clock=lambda: NOW,
    )

    report = worker.run_once(limit=10)

    assert report.completed == 0
    assert report.failed == 1
    assert source.saved[0].status == "FAILED"
    assert source.saved[0].error_type == "RuntimeError"
    assert "secret details" not in str(source.saved[0])
