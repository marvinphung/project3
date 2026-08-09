from __future__ import annotations

from pathlib import Path

from footballpulse_crawler_service.extraction.extractors import (
    BeautifulSoupExtractor,
    ExtractedContent,
    ExtractionPipeline,
    ExtractionStatus,
    ExtractorName,
    TrafilaturaExtractor,
)

FIXTURES = Path(__file__).parents[3] / "tests" / "fixtures" / "mock-news" / "articles"


def test_trafilatura_extracts_main_fixture_content_and_title() -> None:
    html = (FIXTURES / "vinicius-12.html").read_bytes()

    result = TrafilaturaExtractor().extract(
        html,
        url="https://trusted-a.test/football/vinicius-offer",
    )

    assert result is not None
    assert result.title == "Arsenal submit €180m Vinicius offer"
    assert "Arsenal have submitted a formal offer worth €180 million" in result.text
    assert "Real Madrid have not yet responded" in result.text


def test_pipeline_uses_beautifulsoup_as_explicit_partial_fallback() -> None:
    class EmptyPrimary:
        def extract(self, html: bytes, *, url: str) -> ExtractedContent | None:
            del html, url
            return None

    html = b"""<html><head><title>Fallback title</title></head><body>
    <nav>Navigation</nav><article><h1>Fallback heading</h1>
    <p>This is enough useful article content for the fallback extractor.</p>
    <script>tracking()</script></article></body></html>"""
    pipeline = ExtractionPipeline(primary=EmptyPrimary(), fallback=BeautifulSoupExtractor())

    result = pipeline.extract(html, url="https://news.example.com/article")

    assert result.status is ExtractionStatus.PARTIAL
    assert result.extractor is ExtractorName.BEAUTIFULSOUP
    assert result.title == "Fallback heading"
    assert result.text == (
        "Fallback heading This is enough useful article content for the fallback extractor."
    )
    assert "Navigation" not in result.text
    assert "tracking" not in result.text
    assert result.diagnostics == ("primary_extractor_returned_no_content",)


def test_pipeline_returns_explicit_failure_instead_of_empty_success() -> None:
    class EmptyExtractor:
        def extract(self, html: bytes, *, url: str) -> None:
            del html, url
            return None

    pipeline = ExtractionPipeline(primary=EmptyExtractor(), fallback=EmptyExtractor())

    result = pipeline.extract(b"<html></html>", url="https://news.example.com/empty")

    assert result.status is ExtractionStatus.FAILED
    assert result.extractor is None
    assert result.title is None
    assert result.text is None
    assert result.diagnostics == (
        "primary_extractor_returned_no_content",
        "fallback_extractor_returned_no_content",
    )
