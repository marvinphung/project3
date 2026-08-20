from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from footballpulse_event_contracts import (
    ArticleCleanedEvent,
    ArticleDiscoveredEvent,
    event_json_schema,
)
from pydantic import BaseModel, TypeAdapter, ValidationError

FIXTURES = Path(__file__).parent / "fixtures"
SCHEMAS = Path(__file__).parents[2] / "contracts" / "events"
JSON_OBJECT = TypeAdapter(dict[str, Any])


def load_json(path: Path) -> dict[str, Any]:
    return JSON_OBJECT.validate_python(json.loads(path.read_text(encoding="utf-8")))


@pytest.mark.parametrize(
    ("model", "fixture_name"),
    [
        (ArticleDiscoveredEvent, "article_discovered_v1.valid.json"),
        (ArticleCleanedEvent, "article_cleaned_v1.valid.json"),
    ],
)
def test_valid_event_fixtures_round_trip(model: type[BaseModel], fixture_name: str) -> None:
    fixture = load_json(FIXTURES / fixture_name)

    event = model.model_validate(fixture)

    assert event.model_dump(mode="json") == fixture


@pytest.mark.parametrize(
    ("model", "fixture_name"),
    [
        (ArticleDiscoveredEvent, "article_discovered_v1.invalid.json"),
        (ArticleCleanedEvent, "article_cleaned_v1.invalid.json"),
    ],
)
def test_invalid_event_fixtures_are_rejected(model: type[BaseModel], fixture_name: str) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(load_json(FIXTURES / fixture_name))


def test_envelope_requires_timezone_aware_timestamp() -> None:
    fixture = load_json(FIXTURES / "article_discovered_v1.valid.json")
    fixture["occurred_at"] = "2026-08-01T00:02:00"

    with pytest.raises(ValidationError):
        ArticleDiscoveredEvent.model_validate(fixture)


@pytest.mark.parametrize(
    ("model", "fixture_name", "forbidden_field"),
    [
        (ArticleDiscoveredEvent, "article_discovered_v1.valid.json", "raw_html"),
        (ArticleCleanedEvent, "article_cleaned_v1.valid.json", "cleaned_content"),
    ],
)
def test_event_payload_rejects_unbounded_evidence(
    model: type[BaseModel], fixture_name: str, forbidden_field: str
) -> None:
    fixture = load_json(FIXTURES / fixture_name)
    fixture["payload"][forbidden_field] = "must stay outside Kafka"

    with pytest.raises(ValidationError):
        model.model_validate(fixture)


def test_duplicate_result_requires_matching_reference() -> None:
    fixture = load_json(FIXTURES / "article_cleaned_v1.valid.json")
    fixture["payload"]["duplicate_type"] = "EXACT"

    with pytest.raises(ValidationError, match="duplicate reference"):
        ArticleCleanedEvent.model_validate(fixture)


@pytest.mark.parametrize(
    ("model", "schema_path"),
    [
        (ArticleDiscoveredEvent, SCHEMAS / "article.discovered" / "v1.schema.json"),
        (ArticleCleanedEvent, SCHEMAS / "article.cleaned" / "v1.schema.json"),
    ],
)
def test_committed_json_schema_matches_runtime_model(
    model: type[BaseModel], schema_path: Path
) -> None:
    assert load_json(schema_path) == event_json_schema(model)
