from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from footballpulse_event_contracts import NewsCrawledEvent, event_json_schema
from pydantic import TypeAdapter

FIXTURES = Path(__file__).parent / "fixtures"
SCHEMAS = Path(__file__).parents[2] / "contracts" / "events"
JSON_OBJECT = TypeAdapter(dict[str, Any])


def load_json(path: Path) -> dict[str, Any]:
    return JSON_OBJECT.validate_python(json.loads(path.read_text(encoding="utf-8")))


def test_valid_news_crawled_fixture_round_trip() -> None:
    fixture = load_json(FIXTURES / "news_crawled_v1.valid.json")
    event = NewsCrawledEvent.model_validate(fixture)
    assert event.model_dump(mode="json") == fixture


def test_news_crawled_schema_matches_runtime_model() -> None:
    schema_path = SCHEMAS / "news.crawled" / "v1.schema.json"
    assert load_json(schema_path) == event_json_schema(NewsCrawledEvent)
