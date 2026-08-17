from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from importlib import import_module
from typing import Protocol, cast

from footballpulse_intelligence_service.application.entity_extraction import ModelSpan
from footballpulse_intelligence_service.domain.entity import EntityType
from footballpulse_intelligence_service.domain.extraction import EntityLabel

DEFAULT_GLINER_MODEL = "urchade/gliner_small-v2.1"

_ENTITY_LABELS = {
    EntityType.PLAYER: EntityLabel.PLAYER,
    EntityType.CLUB: EntityLabel.CLUB,
    EntityType.COACH: EntityLabel.COACH,
    EntityType.COMPETITION: EntityLabel.COMPETITION,
}


class GlinerModel(Protocol):
    def predict_entities(
        self,
        text: str,
        labels: list[str],
        *,
        threshold: float,
    ) -> list[dict[str, object]]: ...


def _load_gliner(model_id: str) -> GlinerModel:
    try:
        gliner_class = import_module("gliner").GLiNER
    except (ImportError, AttributeError) as error:
        raise RuntimeError(
            "GLiNER runtime is unavailable; install the intelligence-service model extra"
        ) from error
    return cast(GlinerModel, gliner_class.from_pretrained(model_id))


class GlinerEntityExtractor:
    model_name = "gliner"

    def __init__(
        self,
        *,
        model_id: str = DEFAULT_GLINER_MODEL,
        model_loader: Callable[[str], GlinerModel] = _load_gliner,
    ) -> None:
        self.model_version = model_id
        self._model_id = model_id
        self._model_loader = model_loader
        self._model: GlinerModel | None = None

    def extract(
        self,
        text: str,
        *,
        labels: tuple[EntityLabel, ...],
        threshold: float,
    ) -> list[ModelSpan]:
        if not 0 <= threshold <= 1:
            raise ValueError("GLiNER threshold must be between 0 and 1")
        model = self._model
        if model is None:
            model = self._model_loader(self._model_id)
            self._model = model
        raw_predictions = model.predict_entities(
            text,
            [label.value for label in labels],
            threshold=threshold,
        )
        if not isinstance(raw_predictions, list):
            raise ValueError("invalid GLiNER model output: expected a list")
        return [self._parse_prediction(item, text) for item in raw_predictions]

    @staticmethod
    def _parse_prediction(item: object, source_text: str) -> ModelSpan:
        if not isinstance(item, Mapping):
            raise ValueError("invalid GLiNER model output: prediction must be an object")
        text = item.get("text")
        label = item.get("label")
        start = item.get("start")
        end = item.get("end")
        score = item.get("score")
        if (
            not isinstance(text, str)
            or not isinstance(label, str)
            or not isinstance(start, int)
            or isinstance(start, bool)
            or not isinstance(end, int)
            or isinstance(end, bool)
            or not isinstance(score, int | float)
            or isinstance(score, bool)
        ):
            raise ValueError("invalid GLiNER model output: fields have unexpected types")
        try:
            entity_label = EntityLabel(label)
        except ValueError as error:
            raise ValueError("invalid GLiNER model output: unknown entity label") from error
        numeric_score = float(score)
        if start < 0 or end <= start or end > len(source_text):
            raise ValueError("invalid GLiNER model output: offsets are outside input")
        if source_text[start:end] != text:
            raise ValueError("invalid GLiNER model output: text does not match offsets")
        if not 0 <= numeric_score <= 1:
            raise ValueError("invalid GLiNER model output: score is outside range")
        return ModelSpan(text, entity_label, start, end, numeric_score)


@dataclass(frozen=True, slots=True)
class MockEntityRule:
    text: str
    label: EntityLabel
    score: float

    def __post_init__(self) -> None:
        if not self.text:
            raise ValueError("mock entity rule text must not be empty")
        if not 0 <= self.score <= 1:
            raise ValueError("mock entity rule score must be between 0 and 1")


class MockEntityExtractor:
    model_name = "mock-gliner"
    model_version = "fixture-v1"

    def __init__(self, *, rules: tuple[MockEntityRule, ...]) -> None:
        self._rules = rules

    def extract(
        self,
        text: str,
        *,
        labels: tuple[EntityLabel, ...],
        threshold: float,
    ) -> list[ModelSpan]:
        predictions: list[ModelSpan] = []
        allowed_labels = set(labels)
        for rule in self._rules:
            if rule.label not in allowed_labels or rule.score < threshold or not rule.text:
                continue
            start = text.find(rule.text)
            while start >= 0:
                predictions.append(
                    ModelSpan(rule.text, rule.label, start, start + len(rule.text), rule.score)
                )
                start = text.find(rule.text, start + len(rule.text))
        return sorted(
            predictions,
            key=lambda prediction: (prediction.start, prediction.end, prediction.label.value),
        )


@dataclass(frozen=True, slots=True)
class CatalogEntityRule:
    alias: str
    entity_type: EntityType

    def __post_init__(self) -> None:
        if not self.alias.strip():
            raise ValueError("catalog alias must not be empty")


class CatalogAliasEntityExtractor:
    """Deterministic offline extractor backed only by reviewed catalog aliases."""

    model_name = "catalog-alias"
    model_version = "catalog-v1"

    def __init__(self, *, rules: tuple[CatalogEntityRule, ...]) -> None:
        self._rules = tuple(
            sorted(rules, key=lambda rule: (-len(rule.alias), rule.alias.casefold()))
        )

    def extract(
        self,
        text: str,
        *,
        labels: tuple[EntityLabel, ...],
        threshold: float,
    ) -> list[ModelSpan]:
        if not 0 <= threshold <= 1:
            raise ValueError("catalog threshold must be between 0 and 1")
        allowed_labels = set(labels)
        predictions: list[ModelSpan] = []
        for rule in self._rules:
            label = _ENTITY_LABELS[rule.entity_type]
            if label not in allowed_labels:
                continue
            pattern = re.compile(rf"(?<!\w){re.escape(rule.alias)}(?!\w)", re.IGNORECASE)
            for match in pattern.finditer(text):
                predictions.append(ModelSpan(match.group(), label, match.start(), match.end(), 1.0))
        return sorted(
            predictions,
            key=lambda prediction: (prediction.start, prediction.end, prediction.label.value),
        )
