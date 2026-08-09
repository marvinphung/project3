from __future__ import annotations

from footballpulse_intelligence_service.adapters.entity_extractors import (
    GlinerEntityExtractor,
    MockEntityExtractor,
    MockEntityRule,
)
from footballpulse_intelligence_service.domain.extraction import EntityLabel


class RecordingModel:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str], float]] = []

    def predict_entities(
        self,
        text: str,
        labels: list[str],
        *,
        threshold: float,
    ) -> list[dict[str, object]]:
        self.calls.append((text, labels, threshold))
        return [
            {
                "text": "Vinicius Junior",
                "label": "football player",
                "start": 9,
                "end": 24,
                "score": 0.91,
            }
        ]


def test_gliner_adapter_lazy_loads_once_and_validates_contract() -> None:
    model = RecordingModel()
    load_count = 0

    def loader(model_id: str) -> RecordingModel:
        nonlocal load_count
        load_count += 1
        assert model_id == "urchade/gliner_small-v2.1"
        return model

    extractor = GlinerEntityExtractor(model_loader=loader)
    text = "Arsenal: Vinicius Junior update"

    first = extractor.extract(text, labels=tuple(EntityLabel), threshold=0.5)
    second = extractor.extract(text, labels=tuple(EntityLabel), threshold=0.6)

    assert first[0].text == "Vinicius Junior"
    assert first[0].label is EntityLabel.PLAYER
    assert second == first
    assert load_count == 1
    assert model.calls[0][1] == [label.value for label in EntityLabel]
    assert model.calls[0][2] == 0.5


def test_gliner_adapter_rejects_untrusted_model_output() -> None:
    class InvalidModel(RecordingModel):
        def predict_entities(
            self,
            text: str,
            labels: list[str],
            *,
            threshold: float,
        ) -> list[dict[str, object]]:
            del text, labels, threshold
            return [{"text": "Arsenal", "label": "malicious type", "start": 0, "end": 7}]

    extractor = GlinerEntityExtractor(model_loader=lambda model_id: InvalidModel())

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
    assert extractor.model_name == "mock-gliner"


def test_mock_rule_rejects_invalid_fixture_confidence() -> None:
    try:
        MockEntityRule("Arsenal", EntityLabel.CLUB, 1.01)
    except ValueError as error:
        assert "score" in str(error)
    else:
        raise AssertionError("invalid mock confidence must be rejected")
