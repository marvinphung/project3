from collections.abc import Mapping

from footballpulse_intelligence_service.adapters.entity_extractors import (
    CatalogAliasEntityExtractor,
    CatalogEntityRule,
    GlinerEntityExtractor,
    MockEntityExtractor,
    MockEntityRule,
)
from footballpulse_intelligence_service.domain.entity import EntityType
from footballpulse_intelligence_service.domain.extraction import EntityLabel


class RecordingModel:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Mapping[str, str] | list[str], float]] = []

    def extract_entities(
        self,
        text: str,
        entity_types: Mapping[str, str] | list[str],
        *,
        threshold: float = 0.5,
        format_results: bool = True,
        include_confidence: bool = True,
        include_spans: bool = True,
    ) -> dict[str, object]:
        self.calls.append((text, entity_types, threshold))
        return {
            "entities": {
                "player": [
                    {
                        "text": "Vinicius Junior",
                        "confidence": 0.91,
                        "start": 9,
                        "end": 24,
                    }
                ]
            }
        }


def test_gliner_adapter_lazy_loads_once_and_validates_contract() -> None:
    model = RecordingModel()
    load_count = 0

    def loader(model_id: str, device: str = "cpu") -> RecordingModel:
        nonlocal load_count
        load_count += 1
        assert model_id == "fastino/gliner2-large-v1"
        assert device == "cpu"
        return model

    extractor = GlinerEntityExtractor(model_loader=loader)
    text = "Arsenal: Vinicius Junior update"

    first = extractor.extract(text, labels=tuple(EntityLabel), threshold=0.5)
    second = extractor.extract(text, labels=tuple(EntityLabel), threshold=0.6)

    assert first[0].text == "Vinicius Junior"
    assert first[0].label is EntityLabel.PLAYER
    assert second == first
    assert load_count == 1
    assert set(model.calls[0][1].keys()) == {label.value for label in EntityLabel}
    assert model.calls[0][2] == 0.5


def test_gliner_adapter_rejects_untrusted_model_output() -> None:
    class InvalidModel(RecordingModel):
        def extract_entities(
            self,
            text: str,
            entity_types: Mapping[str, str] | list[str],
            *,
            threshold: float = 0.5,
            format_results: bool = True,
            include_confidence: bool = True,
            include_spans: bool = True,
        ) -> dict[str, object]:
            del text, entity_types, threshold, format_results, include_confidence, include_spans
            return {
                "entities": {
                    "malicious type": [{"text": "Arsenal", "start": 0, "end": 7, "confidence": 0.9}]
                }
            }

    extractor = GlinerEntityExtractor(model_loader=lambda model_id, device="cpu": InvalidModel())

    try:
        extractor.extract("Arsenal update", labels=tuple(EntityLabel), threshold=0.5)
    except ValueError as error:
        assert "model output" in str(error)
    else:
        raise AssertionError("invalid model output must not cross the adapter boundary")


def test_mock_extractor_is_deterministic_and_finds_repeated_mentions() -> None:
    extractor = MockEntityExtractor(rules=(MockEntityRule("Arsenal", EntityLabel.CLUB, 0.93),))

    predictions = extractor.extract(
        "Arsenal met Arsenal.", labels=(EntityLabel.CLUB,), threshold=0.5
    )

    assert [(span.start, span.end) for span in predictions] == [(0, 7), (12, 19)]
    assert extractor.model_name == "mock-gliner2"


def test_mock_rule_rejects_invalid_fixture_confidence() -> None:
    try:
        MockEntityRule("Arsenal", EntityLabel.CLUB, 1.01)
    except ValueError as error:
        assert "score" in str(error)
    else:
        raise AssertionError("invalid mock confidence must be rejected")


def test_catalog_alias_extractor_is_case_insensitive_and_prefers_catalog_labels() -> None:
    extractor = CatalogAliasEntityExtractor(
        rules=(
            CatalogEntityRule("Real Madrid", EntityType.CLUB),
            CatalogEntityRule("Vinicius Junior", EntityType.PLAYER),
        )
    )

    predictions = extractor.extract(
        "REAL MADRID opened talks with Vinicius Junior.",
        labels=tuple(EntityLabel),
        threshold=0.5,
    )

    assert [(item.text, item.label, item.start, item.end) for item in predictions] == [
        ("REAL MADRID", EntityLabel.CLUB, 0, 11),
        ("Vinicius Junior", EntityLabel.PLAYER, 30, 45),
    ]
    assert extractor.model_name == "catalog-alias"


def test_catalog_alias_extractor_does_not_match_inside_another_word() -> None:
    extractor = CatalogAliasEntityExtractor(rules=(CatalogEntityRule("Real", EntityType.CLUB),))

    predictions = extractor.extract(
        "The surrealistic report mentioned Real.",
        labels=(EntityLabel.CLUB,),
        threshold=0.5,
    )

    assert [(item.text, item.start) for item in predictions] == [("Real", 34)]
