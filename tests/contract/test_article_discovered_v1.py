import json
from pathlib import Path
from typing import Any, cast

import pytest
from footballpulse_event_contracts import ArticleDiscoveredV1
from jsonschema import Draft202012Validator
from pydantic import ValidationError

FIXTURE_DIR = Path(__file__).parent / "fixtures"
SCHEMA_PATH = (
    Path(__file__).parents[2]
    / "contracts"
    / "events"
    / "article.discovered"
    / "v1.schema.json"
)


def load_fixture() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(
            (FIXTURE_DIR / "article-discovered.v1.valid.json").read_text(
                encoding="utf-8"
            )
        ),
    )


def test_valid_fixture_matches_pydantic_and_json_schema() -> None:
    event = ArticleDiscoveredV1.model_validate(load_fixture())
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(event.model_dump(mode="json", by_alias=True))

    assert event.payload.discovery_id == event.aggregate_id


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("event_type", "article.unique"),
        ("schema_version", 2),
        ("producer", "article-service"),
        ("occurred_at", "2026-07-31T02:00:00"),
    ],
)
def test_rejects_invalid_envelope_values(field: str, value: object) -> None:
    raw_event = load_fixture()
    raw_event[field] = value

    with pytest.raises(ValidationError):
        ArticleDiscoveredV1.model_validate(raw_event)


def test_rejects_unknown_fields_including_raw_html() -> None:
    raw_event = load_fixture()
    raw_event["payload"]["raw_html"] = "<html>not allowed</html>"

    with pytest.raises(ValidationError):
        ArticleDiscoveredV1.model_validate(raw_event)


def test_rejects_aggregate_id_that_differs_from_discovery_id() -> None:
    raw_event = load_fixture()
    raw_event["aggregate_id"] = "019c1f5a-c405-7d4b-95e8-61847f78fe60"

    with pytest.raises(ValidationError):
        ArticleDiscoveredV1.model_validate(raw_event)


@pytest.mark.parametrize(
    ("container", "field"),
    [
        ("envelope", "causation_id"),
        ("payload", "response_headers"),
    ],
)
def test_rejects_missing_required_contract_fields(container: str, field: str) -> None:
    raw_event = load_fixture()
    target = raw_event if container == "envelope" else raw_event["payload"]
    del target[field]

    with pytest.raises(ValidationError):
        ArticleDiscoveredV1.model_validate(raw_event)
