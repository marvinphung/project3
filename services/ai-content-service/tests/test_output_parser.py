from __future__ import annotations

from pathlib import Path

import pytest
from footballpulse_ai_content_service.contracts.batch import BATCH_RECORD_ADAPTER
from footballpulse_ai_content_service.contracts.enrichment import ArticleEnrichmentOutput
from footballpulse_ai_content_service.validation.output_parser import (
    AIOutputInvalidError,
    parse_output_with_one_repair,
)


class RecordingRepairer:
    def __init__(self, repaired: str) -> None:
        self.repaired = repaired
        self.calls: list[tuple[str, str]] = []

    def repair(self, raw_output: str, validation_error: str) -> str:
        self.calls.append((raw_output, validation_error))
        return self.repaired


VALID_JSON = """{
  "contract_version": "article-enrichment.v1",
  "article_version_id": "018f8b45-b634-7c81-a47d-9a7c2f3c3101",
  "input_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "event_type": "TRANSFER",
  "summary_en": "Arsenal reportedly submitted an offer.",
  "claims": [{
    "subject_entity_id": "018f8b45-b634-7c81-a47d-9a7c2f3c8103",
    "predicate": "SUBMITTED_BID",
    "object_entity_id": "018f8b45-b634-7c81-a47d-9a7c2f3c8101",
    "object_text": null,
    "qualifiers": {
      "amount": 180000000,
      "currency": "EUR",
      "date": null,
      "injury": null,
      "score": null
    },
    "certainty": "REPORTED",
    "evidence_quote": "Arsenal reportedly submitted an offer.",
    "evidence_start": 0,
    "evidence_end": 39
  }],
  "model_version": "fixture",
  "prompt_version": "article-enrichment-v1"
}"""
FIXTURES = Path(__file__).parents[3] / "tests" / "fixtures" / "ai"


def test_valid_output_does_not_spend_repair_budget() -> None:
    repairer = RecordingRepairer(VALID_JSON)

    output = parse_output_with_one_repair(VALID_JSON, repairer=repairer)

    assert isinstance(output, ArticleEnrichmentOutput)
    assert repairer.calls == []


def test_invalid_structure_gets_exactly_one_repair_attempt() -> None:
    repairer = RecordingRepairer(VALID_JSON)

    output = parse_output_with_one_repair('{"broken":', repairer=repairer)

    assert output.event_type.value == "TRANSFER"
    assert len(repairer.calls) == 1


def test_failed_repair_is_not_retried_forever() -> None:
    repairer = RecordingRepairer('{"still":"invalid"}')

    with pytest.raises(AIOutputInvalidError):
        parse_output_with_one_repair('{"broken":', repairer=repairer)

    assert len(repairer.calls) == 1


def test_jsonl_fixture_records_are_independent() -> None:
    valid_lines = (FIXTURES / "valid-results.jsonl").read_text().splitlines()
    assert all(BATCH_RECORD_ADAPTER.validate_json(line) for line in valid_lines)

    partial_lines = (FIXTURES / "partial-results.jsonl").read_text().splitlines()
    assert {BATCH_RECORD_ADAPTER.validate_json(line).status for line in partial_lines} == {
        "SUCCESS",
        "ERROR",
    }
