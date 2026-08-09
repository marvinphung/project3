from __future__ import annotations

from pathlib import Path

import pytest
from footballpulse_crawler_service.extraction.processor import ArticleContentProcessor

FIXTURES = Path(__file__).parents[3] / "tests" / "fixtures" / "mock-news" / "articles"

EXPECTED = {
    "vinicius-00.html": (
        "Real open Vinicius renewal talks",
        "Real Madrid open contract talks with Vinícius Júnior Real Madrid have opened talks "
        "with forward Vinícius Júnior over a new contract. The Brazil international remains "
        "an important part of the club's plans.",
    ),
    "vinicius-12.html": (
        "Arsenal submit €180m Vinicius offer",
        "Arsenal send €180m offer to Real Madrid for Vinícius Júnior Arsenal have submitted "
        "a formal offer worth €180 million to Real Madrid for Vinícius Júnior. Real Madrid "
        "have not yet responded to the proposal.",
    ),
    "vinicius-06.html": (
        "Arsenal contact Vinicius representatives",
        "Arsenal make contact over Vinicius Arsenal have contacted representatives of "
        "Vinicius Junior about a possible transfer from Real Madrid. No formal offer has "
        "been submitted.",
    ),
    "vinicius-18-no-change.html": (
        "Arsenal proposal for Vinicius remains €180m",
        "Arsenal wait for response to Vinicius bid Arsenal are still waiting after sending "
        "Real Madrid a €180 million offer for Vinicius Junior. The report adds no new terms "
        "and Real Madrid have not responded.",
    ),
    "vinicius-near-duplicate.html": (
        "Gunners lodge major Vinicius proposal",
        "Gunners lodge major proposal for Real star Arsenal, also known as the Gunners, "
        "lodged an offer valued at €180m for Real Madrid winger Vinícius Júnior. The Spanish "
        "club is considering the bid.",
    ),
    "official-denial.html": (
        "Real Madrid deny accepting Vinicius bid",
        "Real Madrid issue official denial Real Madrid said in an official statement that no "
        "offer for Vinícius Júnior has been accepted.",
    ),
    "injury.html": (
        "Vinicius ruled out with hamstring injury",
        "Vinícius Júnior suffers hamstring injury Real Madrid coach Xabi Alonso said Vini Jr "
        "will miss the La Liga opener with a hamstring injury.",
    ),
    "match.html": (
        "Real Madrid beat Arsenal 2-1",
        "Real Madrid beat Arsenal in friendly Real Madrid defeated Arsenal 2-1 after a late "
        "winner in a pre-season match.",
    ),
}


@pytest.mark.parametrize(("fixture_name", "expected"), EXPECTED.items())
def test_produces_deterministic_clean_content_for_project_fixtures(
    fixture_name: str,
    expected: tuple[str, str],
) -> None:
    html = (FIXTURES / fixture_name).read_bytes()

    result = ArticleContentProcessor().process(
        html,
        url=f"https://trusted-a.test/football/{fixture_name}",
    )

    assert result.status == "SUCCESS"
    assert result.extractor == "TRAFILATURA"
    assert (result.title, result.text) == expected
    assert "\n" not in result.text


def test_keeps_failure_explicit_when_html_has_no_article_content() -> None:
    result = ArticleContentProcessor().process(
        b"<html><body><nav>Home</nav></body></html>",
        url="https://trusted-a.test/empty",
    )

    assert result.status == "FAILED"
    assert result.title is None
    assert result.text is None
    assert result.diagnostics
