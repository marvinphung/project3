from __future__ import annotations

import os
from dataclasses import dataclass

import pytest
from footballpulse_intelligence_service.adapters.entity_extractors import (
    GlinerEntityExtractor,
)
from footballpulse_intelligence_service.application.entity_extraction import ModelSpan
from footballpulse_intelligence_service.domain.extraction import EntityLabel

pytestmark = pytest.mark.skipif(
    os.getenv("FOOTBALLPULSE_RUN_GLINER_ACCEPTANCE") != "1",
    reason="set FOOTBALLPULSE_RUN_GLINER_ACCEPTANCE=1 to load the real local model",
)


@dataclass(frozen=True, slots=True)
class Fixture:
    text: str
    expected: frozenset[tuple[str, EntityLabel]]


FIXTURES = (
    Fixture(
        text=(
            "Manchester United manager Erik ten Hag praised Bruno Fernandes and Marcus Rashford "
            "after the FA Cup final at Wembley."
        ),
        expected=frozenset(
            {
                ("Manchester United", EntityLabel.CLUB),
                ("Erik ten Hag", EntityLabel.COACH),
                ("Bruno Fernandes", EntityLabel.PLAYER),
                ("Marcus Rashford", EntityLabel.PLAYER),
                ("FA Cup", EntityLabel.COMPETITION),
            }
        ),
    ),
    Fixture(
        text=(
            "Arsenal manager Mikel Arteta praised Bukayo Saka after Arsenal beat Liverpool "
            "in the Premier League."
        ),
        expected=frozenset(
            {
                ("Arsenal", EntityLabel.CLUB),
                ("Mikel Arteta", EntityLabel.COACH),
                ("Bukayo Saka", EntityLabel.PLAYER),
                ("Liverpool", EntityLabel.CLUB),
                ("Premier League", EntityLabel.COMPETITION),
            }
        ),
    ),
    Fixture(
        text=(
            "Pep Guardiola said Erling Haaland will start for Manchester City "
            "in the Champions League."
        ),
        expected=frozenset(
            {
                ("Pep Guardiola", EntityLabel.COACH),
                ("Erling Haaland", EntityLabel.PLAYER),
                ("Manchester City", EntityLabel.CLUB),
                ("Champions League", EntityLabel.COMPETITION),
            }
        ),
    ),
    Fixture(
        text="Manchester United played the FA Cup final at Wembley.",
        expected=frozenset(
            {
                ("Manchester United", EntityLabel.CLUB),
                ("FA Cup", EntityLabel.COMPETITION),
            }
        ),
    ),
    Fixture(
        text="The weather was warm and the stadium opened at noon.",
        expected=frozenset(),
    ),
)


def _identity(span: ModelSpan) -> tuple[str, EntityLabel]:
    return span.text, span.label


def test_real_gliner_football_fixture_quality() -> None:
    extractor = GlinerEntityExtractor()
    true_positive = 0
    predicted_count = 0
    expected_count = 0
    unresolved_examples: list[str] = []

    for fixture in FIXTURES:
        predictions = extractor.extract(
            fixture.text,
            labels=tuple(EntityLabel),
            threshold=0.5,
        )
        predicted = {_identity(span) for span in predictions}
        true_positive += len(predicted & fixture.expected)
        predicted_count += len(predicted)
        expected_count += len(fixture.expected)
        unresolved_examples.extend(
            f"{text} [{label.value}]" for text, label in sorted(predicted - fixture.expected)
        )

    precision = true_positive / predicted_count if predicted_count else 0.0
    recall = true_positive / expected_count
    print(
        "GLiNER fixture benchmark: "
        f"precision={precision:.3f}, recall={recall:.3f}, "
        f"true_positive={true_positive}, predicted={predicted_count}, "
        f"expected={expected_count}, extras={unresolved_examples}"
    )

    assert predicted_count == 16
    assert expected_count == 16
    assert precision == 1.0
    assert recall == 1.0
