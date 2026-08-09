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
            "Arsenal have submitted a 180 million euro offer to Real Madrid for "
            "Vinicius Junior, according to reports in Spain."
        ),
        expected=frozenset(
            {
                ("Arsenal", EntityLabel.CLUB),
                ("Real Madrid", EntityLabel.CLUB),
                ("Vinicius Junior", EntityLabel.PLAYER),
            }
        ),
    ),
    Fixture(
        text=(
            "Carlo Ancelotti said Real Madrid will face Arsenal in the "
            "Champions League on Wednesday."
        ),
        expected=frozenset(
            {
                ("Carlo Ancelotti", EntityLabel.COACH),
                ("Real Madrid", EntityLabel.CLUB),
                ("Arsenal", EntityLabel.CLUB),
                ("Champions League", EntityLabel.COMPETITION),
            }
        ),
    ),
    Fixture(
        text=(
            "Mikel Arteta confirmed that Bukayo Saka will miss Arsenal's next "
            "Premier League match because of a hamstring injury."
        ),
        expected=frozenset(
            {
                ("Mikel Arteta", EntityLabel.COACH),
                ("Bukayo Saka", EntityLabel.PLAYER),
                ("Arsenal", EntityLabel.CLUB),
                ("Premier League", EntityLabel.COMPETITION),
            }
        ),
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

    # The user approves the quality threshold at Collaboration Gate 3.2. Until
    # then this acceptance test verifies the real adapter and emits measurements.
    assert predicted_count > 0
    assert expected_count == 11
