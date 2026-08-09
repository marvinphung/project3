from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from footballpulse_intelligence_service.application.entity_extraction import (
    EntityExtractionPipeline,
    ExtractionRequest,
    ModelSpan,
    ResolutionStatus,
)
from footballpulse_intelligence_service.domain.entity import Entity, EntityType
from footballpulse_intelligence_service.domain.extraction import EntityLabel
from footballpulse_intelligence_service.domain.unresolved import UnresolvedEntityMention

ARTICLE_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c9101")
VINICIUS_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c8101")
ARSENAL_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c8103")
NOW = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)


def _entity(entity_id: UUID, entity_type: EntityType, name: str, slug: str) -> Entity:
    return Entity.create(
        entity_id=entity_id,
        entity_type=entity_type,
        canonical_name=name,
        slug=slug,
        now=NOW,
    )


class FixtureExtractor:
    model_name = "mock-gliner"
    model_version = "fixture-v1"

    def extract(
        self,
        text: str,
        *,
        labels: tuple[EntityLabel, ...],
        threshold: float,
    ) -> list[ModelSpan]:
        del labels
        fixtures = (
            ("Arsenal", EntityLabel.CLUB, 0.92),
            ("Vinicius Junior", EntityLabel.PLAYER, 0.89),
            ("Mystery FC", EntityLabel.CLUB, 0.81),
            ("Unknown Cup", EntityLabel.COMPETITION, 0.61),
        )
        return [
            ModelSpan(value, label, text.index(value), text.index(value) + len(value), score)
            for value, label, score in fixtures
            if value in text and score >= threshold
        ]


class FixtureResolver:
    def __init__(self) -> None:
        self.entities = {
            "arsenal": _entity(ARSENAL_ID, EntityType.CLUB, "Arsenal", "arsenal"),
            "vinicius junior": _entity(
                VINICIUS_ID,
                EntityType.PLAYER,
                "Vinícius Júnior",
                "vinicius-junior",
            ),
        }

    def resolve(self, alias: str) -> Entity | None:
        return self.entities.get(alias)


class RecordingUnresolvedRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, UnresolvedEntityMention] = {}

    def add_once(self, mention: UnresolvedEntityMention) -> UnresolvedEntityMention:
        return self.items.setdefault(mention.id, mention)


def test_resolves_exact_aliases_and_records_only_high_confidence_unresolved() -> None:
    unresolved = RecordingUnresolvedRepository()
    pipeline = EntityExtractionPipeline(
        extractor=FixtureExtractor(),
        resolver=FixtureResolver(),
        unresolved_repository=unresolved,
        clock=lambda: NOW,
        detection_threshold=0.5,
        review_threshold=0.75,
        max_words_per_chunk=300,
        overlap_words=40,
    )

    result = pipeline.process(
        ExtractionRequest(
            article_version_id=ARTICLE_ID,
            title="Arsenal submit Vinicius Junior update",
            cleaned_content=(
                "Arsenal contacted Vinicius Junior while Mystery FC joined the talks. "
                "The Unknown Cup was also mentioned."
            ),
        )
    )

    mentions = {(mention.prediction.text, mention.status): mention for mention in result.mentions}
    assert mentions[("Arsenal", ResolutionStatus.RESOLVED)].entity_id == ARSENAL_ID
    assert mentions[("Vinicius Junior", ResolutionStatus.RESOLVED)].entity_id == VINICIUS_ID
    assert mentions[("Mystery FC", ResolutionStatus.UNRESOLVED)].entity_id is None
    assert mentions[("Unknown Cup", ResolutionStatus.UNRESOLVED)].entity_id is None
    assert {item.mention_text for item in unresolved.items.values()} == {"Mystery FC"}
    assert result.model_name == "mock-gliner"
    assert result.detection_threshold == 0.5
    assert result.review_threshold == 0.75


def test_wrong_entity_type_is_unresolved_even_when_alias_exists() -> None:
    class WrongLabelExtractor(FixtureExtractor):
        def extract(
            self,
            text: str,
            *,
            labels: tuple[EntityLabel, ...],
            threshold: float,
        ) -> list[ModelSpan]:
            del labels, threshold
            start = text.index("Arsenal")
            return [ModelSpan("Arsenal", EntityLabel.PLAYER, start, start + 7, 0.95)]

    unresolved = RecordingUnresolvedRepository()
    pipeline = EntityExtractionPipeline(
        extractor=WrongLabelExtractor(),
        resolver=FixtureResolver(),
        unresolved_repository=unresolved,
        clock=lambda: NOW,
    )

    result = pipeline.process(
        ExtractionRequest(ARTICLE_ID, "Arsenal update", "Arsenal submitted an offer.")
    )

    assert all(mention.status is ResolutionStatus.UNRESOLVED for mention in result.mentions)
    assert all(mention.entity_id is None for mention in result.mentions)
