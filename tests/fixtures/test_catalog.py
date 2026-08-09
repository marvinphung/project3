from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID
from xml.etree import ElementTree

import pytest
from pydantic import TypeAdapter

ROOT = Path(__file__).parents[2]
CATALOG_PATH = ROOT / "tests/fixtures/mock-news/catalog.json"
JSON_OBJECT = TypeAdapter(dict[str, Any])


def load_catalog() -> dict[str, Any]:
    return JSON_OBJECT.validate_json(CATALOG_PATH.read_text(encoding="utf-8"))


def fixture_path(relative_path: str) -> Path:
    return ROOT / relative_path


def test_catalog_has_unique_stable_ids_and_aware_timestamps() -> None:
    catalog = load_catalog()
    records = [*catalog["sources"], *catalog["articles"]]
    identifiers = [record["id"] for record in records]

    assert len(identifiers) == len(set(identifiers))
    assert all(UUID(identifier) for identifier in identifiers)
    assert all(
        datetime.fromisoformat(article["discovered_at"]).tzinfo is not None
        for article in catalog["articles"]
    )


def test_every_successful_article_fixture_exists_and_matches_sha256() -> None:
    for article in load_catalog()["articles"]:
        if article["transport"]["status"] != 200:
            assert article["fixture"] is None
            assert article["sha256"] is None
            continue

        article_path = fixture_path(article["fixture"])
        digest = hashlib.sha256(article_path.read_bytes()).hexdigest()
        assert digest == article["sha256"]


def test_rss_fixtures_are_local_valid_xml_with_known_article_urls() -> None:
    catalog = load_catalog()
    known_urls = {article["url"] for article in catalog["articles"]}

    for source in catalog["sources"]:
        rss_path = fixture_path(source["rss_fixture"])
        root = ElementTree.parse(rss_path).getroot()
        links = {link.text for link in root.findall("./channel/item/link")}
        assert links
        assert links <= known_urls


def test_transfer_timeline_oracle_skips_18h_without_material_change() -> None:
    windows = load_catalog()["timeline_windows"]

    assert [datetime.fromisoformat(window["window_start"]).hour for window in windows] == [
        0,
        6,
        12,
        18,
    ]
    assert [window["creates_timeline_entry"] for window in windows] == [True, True, True, False]
    assert len({window["story_id"] for window in windows}) == 1


def test_catalog_covers_transport_and_content_edge_cases() -> None:
    scenarios = {article["scenario"] for article in load_catalog()["articles"]}

    assert {
        "url_duplicate",
        "exact_duplicate",
        "near_duplicate",
        "official_denial",
        "injury",
        "match",
        "http_429",
        "http_500",
        "timeout",
    } <= scenarios


def test_catalog_references_and_duplicate_oracles_are_consistent() -> None:
    catalog = load_catalog()
    source_ids = {source["id"] for source in catalog["sources"]}
    article_ids = {article["id"] for article in catalog["articles"]}
    articles_by_scenario = {article["scenario"]: article for article in catalog["articles"]}

    assert all(article["source_id"] in source_ids for article in catalog["articles"])
    assert all(set(window["article_ids"]) <= article_ids for window in catalog["timeline_windows"])
    assert (
        articles_by_scenario["url_duplicate"]["sha256"]
        == articles_by_scenario["transfer_00_renewal"]["sha256"]
    )
    assert (
        articles_by_scenario["exact_duplicate"]["sha256"]
        == articles_by_scenario["transfer_12_offer"]["sha256"]
    )
    assert (
        articles_by_scenario["near_duplicate"]["sha256"]
        != articles_by_scenario["transfer_12_offer"]["sha256"]
    )


def test_catalog_contains_player_club_coach_and_competition_aliases() -> None:
    mentions = {
        mention for article in load_catalog()["articles"] for mention in article["entities"]
    }

    assert {"Vini Jr", "Vinicius Junior", "Vinícius Júnior"} <= mentions
    assert {"Real", "Real Madrid", "Gunners", "Arsenal", "Xabi Alonso", "La Liga"} <= mentions


def test_ai_jsonl_fixtures_have_expected_shape() -> None:
    for ai_fixture in load_catalog()["ai_fixtures"]:
        lines = fixture_path(ai_fixture["path"]).read_text(encoding="utf-8").splitlines()
        parsed_lines: list[dict[str, Any]] = []
        invalid_lines = 0
        for line in lines:
            try:
                parsed_lines.append(JSON_OBJECT.validate_json(line))
            except ValueError:
                invalid_lines += 1

        if ai_fixture["kind"] == "valid":
            assert parsed_lines and invalid_lines == 0
        elif ai_fixture["kind"] == "invalid_json":
            assert invalid_lines >= 1
        elif ai_fixture["kind"] == "partial":
            assert invalid_lines == 0
            assert {result["status"] for result in parsed_lines} == {"SUCCESS", "ERROR"}
        else:
            pytest.fail(f"Unknown AI fixture kind: {ai_fixture['kind']}")
