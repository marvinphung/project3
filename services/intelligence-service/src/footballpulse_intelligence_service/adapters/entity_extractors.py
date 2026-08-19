from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from importlib import import_module
from threading import Lock
from typing import Protocol, cast

from footballpulse_runtime_config import log_event

from footballpulse_intelligence_service.application.entity_extraction import ModelSpan
from footballpulse_intelligence_service.domain.entity import EntityType
from footballpulse_intelligence_service.domain.extraction import EntityLabel

DEFAULT_GLINER2_MODEL = "fastino/gliner2-large-v1"
DEFAULT_GLINER_MODEL = DEFAULT_GLINER2_MODEL
LOGGER = logging.getLogger("footballpulse.intelligence.entity_model")

ENTITY_SCHEMA: Mapping[str, str] = {
    "player": (
        "A named professional association football or soccer player. "
        "Examples: Bruno Fernandes, Marcus Rashford, Bukayo Saka, "
        "Mohamed Salah, Kylian Mbappe. "
        "Return the person's name exactly as it appears in the text."
    ),
    "club": (
        "A named association football or soccer club or team. "
        "Examples: Manchester United, Arsenal, Liverpool, Real Madrid, Barcelona. "
        "Do not classify competitions, stadiums, cities, or organizations "
        "that are not football teams as clubs."
    ),
    "competition": (
        "A named association football league, cup, competition, or tournament. "
        "Examples: FA Cup, Premier League, UEFA Champions League, "
        "La Liga, Europa League, World Cup."
    ),
    "coach": (
        "A named association football manager, head coach, assistant coach, "
        "or football coach. "
        "Examples: Erik ten Hag, Pep Guardiola, Mikel Arteta, Carlo Ancelotti. "
        "Classify according to the person's role in the current text."
    ),
}

_ENTITY_LABELS = {
    EntityType.PLAYER: EntityLabel.PLAYER,
    EntityType.CLUB: EntityLabel.CLUB,
    EntityType.COACH: EntityLabel.COACH,
    EntityType.COMPETITION: EntityLabel.COMPETITION,
}


class Gliner2Model(Protocol):
    def extract_entities(
        self,
        text: str,
        entity_types: Mapping[str, str] | list[str],
        *,
        threshold: float = ...,
        format_results: bool = ...,
        include_confidence: bool = ...,
        include_spans: bool = ...,
    ) -> dict[str, object]: ...


GlinerModel = Gliner2Model


def _load_gliner2(model_id: str, device: str = "cpu") -> Gliner2Model:
    try:
        gliner_class = import_module("gliner2").GLiNER2
    except (ImportError, AttributeError) as error:
        raise RuntimeError(
            "GLiNER2 runtime is unavailable; install the intelligence-service model extra"
        ) from error
    return cast(Gliner2Model, gliner_class.from_pretrained(model_id, map_location=device))


_load_gliner = _load_gliner2


ModelLoader = Callable[[str, str], Gliner2Model] | Callable[[str], Gliner2Model]


class GlinerEntityExtractor:
    model_name = "gliner2"

    def __init__(
        self,
        *,
        model_id: str = DEFAULT_GLINER2_MODEL,
        device: str = "cpu",
        model_loader: ModelLoader | None = None,
        schema: Mapping[str, str] | None = None,
    ) -> None:
        self.model_version = model_id
        self._model_id = model_id
        self._device = device
        self._schema = dict(schema or ENTITY_SCHEMA)
        self._model_loader = model_loader
        self._model: Gliner2Model | None = None
        self._lock = Lock()

    def _resolve_loader(self) -> Gliner2Model:
        if self._model_loader is None:
            return _load_gliner2(self._model_id, self._device)
        try:
            return self._model_loader(self._model_id, self._device)  # type: ignore[call-arg]
        except TypeError:
            return self._model_loader(self._model_id)  # type: ignore[call-arg]

    def extract(
        self,
        text: str,
        *,
        labels: tuple[EntityLabel, ...],
        threshold: float,
    ) -> list[ModelSpan]:
        if not 0 <= threshold <= 1:
            raise ValueError("GLiNER2 threshold must be between 0 and 1")
        if not text.strip():
            return []
        model = self._model
        if model is None:
            with self._lock:
                if self._model is None:
                    started = time.monotonic()
                    log_event(
                        LOGGER,
                        "entity_model_loading",
                        model=self._model_id,
                        device=self._device,
                    )
                    self._model = self._resolve_loader()
                    log_event(
                        LOGGER,
                        "entity_model_loaded",
                        model=self._model_id,
                        device=self._device,
                        duration_ms=round((time.monotonic() - started) * 1000),
                    )
                model = self._model

        active_schema = {
            label.value: self._schema.get(label.value, label.value) for label in labels
        }
        if not active_schema:
            return []

        raw_output = model.extract_entities(
            text,
            active_schema,
            threshold=threshold,
            include_confidence=True,
            include_spans=True,
        )
        if not isinstance(raw_output, dict):
            raise ValueError("invalid GLiNER2 model output: expected a dict")

        entities_container = raw_output.get("entities")
        entities_dict = entities_container if isinstance(entities_container, dict) else raw_output

        spans: list[ModelSpan] = []
        for label_key, items in entities_dict.items():
            if not isinstance(items, list):
                continue
            for item in items:
                span = self._parse_prediction(item, label_key, text, threshold)
                if span is not None:
                    spans.append(span)

        return sorted(
            spans,
            key=lambda prediction: (prediction.start, prediction.end, prediction.label.value),
        )

    @staticmethod
    def _parse_prediction(
        item: object,
        label_key: str,
        source_text: str,
        threshold: float,
    ) -> ModelSpan | None:
        if not isinstance(item, Mapping):
            raise ValueError("invalid GLiNER2 model output: prediction must be an object")
        text = item.get("text")
        start = item.get("start")
        end = item.get("end")
        score = item.get("confidence") if item.get("confidence") is not None else item.get("score")
        if (
            not isinstance(text, str)
            or not isinstance(start, int)
            or isinstance(start, bool)
            or not isinstance(end, int)
            or isinstance(end, bool)
            or not isinstance(score, int | float)
            or isinstance(score, bool)
        ):
            raise ValueError("invalid GLiNER2 model output: fields have unexpected types")
        try:
            entity_label = EntityLabel(label_key)
        except ValueError:
            try:
                entity_label = EntityLabel.from_string(label_key)
            except ValueError as error:
                raise ValueError("invalid GLiNER2 model output: unknown entity label") from error
        numeric_score = float(score)
        if start < 0 or end <= start or end > len(source_text):
            raise ValueError("invalid GLiNER2 model output: offsets are outside input")
        if source_text[start:end] != text:
            raise ValueError("invalid GLiNER2 model output: text does not match offsets")
        if not 0 <= numeric_score <= 1:
            raise ValueError("invalid GLiNER2 model output: score is outside range")
        if numeric_score < threshold:
            return None
        return ModelSpan(text, entity_label, start, end, numeric_score)


Gliner2EntityExtractor = GlinerEntityExtractor


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
    model_name = "mock-gliner2"
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
