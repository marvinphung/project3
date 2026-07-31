import hashlib
import json
from pathlib import Path
from typing import Any, cast

FIXTURE_ROOT = Path(__file__).parent / "mock-news"
CATALOG_PATH = FIXTURE_ROOT / "catalog.json"

REQUIRED_SCENARIOS = {
    "transfer-rumour",
    "transfer-alias-update",
    "transfer-exact-url-duplicate",
    "transfer-exact-content-duplicate",
    "transfer-near-duplicate",
    "transfer-official-update",
    "unrelated-injury",
    "unrelated-match",
    "http-429",
    "http-500",
    "slow-response",
    "timeout",
}


def load_catalog() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(CATALOG_PATH.read_text(encoding="utf-8")),
    )


def test_catalog_covers_required_offline_scenarios() -> None:
    catalog = load_catalog()
    scenario_ids = {scenario["id"] for scenario in catalog["scenarios"]}

    assert catalog["schema_version"] == 1
    assert catalog["clock"] == "2026-07-31T00:00:00Z"
    assert REQUIRED_SCENARIOS <= scenario_ids
    assert len(scenario_ids) == len(catalog["scenarios"])


def test_success_scenarios_reference_bounded_local_utf8_fixtures() -> None:
    catalog = load_catalog()

    for scenario in catalog["scenarios"]:
        response = scenario["response"]
        if response["status"] != 200:
            continue

        fixture_path = FIXTURE_ROOT / response["fixture"]
        body = fixture_path.read_text(encoding="utf-8")

        assert fixture_path.is_relative_to(FIXTURE_ROOT)
        assert 0 < len(body.encode()) <= 200_000
        assert response["content_type"] in {"application/rss+xml", "text/html"}


def test_duplicate_and_progression_expectations_are_explicit() -> None:
    scenarios = {item["id"]: item for item in load_catalog()["scenarios"]}

    url_duplicate = scenarios["transfer-exact-url-duplicate"]
    assert url_duplicate["expectation"]["duplicate_of"] == "transfer-rumour"
    assert (
        url_duplicate["request"]["url"]
        == scenarios["transfer-rumour"]["request"]["url"]
    )

    content_duplicate = scenarios["transfer-exact-content-duplicate"]
    original_body = (
        FIXTURE_ROOT / scenarios["transfer-rumour"]["response"]["fixture"]
    ).read_bytes()
    duplicate_body = (
        FIXTURE_ROOT / content_duplicate["response"]["fixture"]
    ).read_bytes()
    assert (
        hashlib.sha256(original_body).digest()
        == hashlib.sha256(duplicate_body).digest()
    )

    near_duplicate = scenarios["transfer-near-duplicate"]
    near_body = (FIXTURE_ROOT / near_duplicate["response"]["fixture"]).read_bytes()
    assert near_body != original_body
    assert near_duplicate["expectation"]["same_story_as"] == "transfer-rumour"

    official = scenarios["transfer-official-update"]
    assert official["available_after_step"] > near_duplicate["available_after_step"]
    assert official["expectation"]["confirmation_level"] == "OFFICIAL"


def test_failure_scenarios_define_deterministic_behavior() -> None:
    scenarios = {item["id"]: item for item in load_catalog()["scenarios"]}

    assert scenarios["http-429"]["response"]["headers"]["Retry-After"] == "2"
    assert scenarios["http-500"]["response"]["status"] == 500
    assert scenarios["slow-response"]["response"]["delay_ms"] == 750
    assert scenarios["timeout"]["response"]["delay_ms"] == 5_000
