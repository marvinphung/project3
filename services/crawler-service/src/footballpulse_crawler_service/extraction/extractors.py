from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

import trafilatura
from bs4 import BeautifulSoup
from trafilatura.settings import Document

_MIN_USEFUL_TEXT_LENGTH = 40


class ExtractorName(StrEnum):
    TRAFILATURA = "TRAFILATURA"
    BEAUTIFULSOUP = "BEAUTIFULSOUP"


class ExtractionStatus(StrEnum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class ExtractedContent:
    title: str | None
    text: str


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    status: ExtractionStatus
    extractor: ExtractorName | None
    title: str | None
    text: str | None
    diagnostics: tuple[str, ...]


class ContentExtractor(Protocol):
    def extract(self, html: bytes, *, url: str) -> ExtractedContent | None: ...


def _useful(title: object, text: object) -> ExtractedContent | None:
    normalized_text = str(text or "").strip()
    if len(normalized_text) < _MIN_USEFUL_TEXT_LENGTH:
        return None
    normalized_title = str(title or "").strip() or None
    return ExtractedContent(normalized_title, normalized_text)


class TrafilaturaExtractor:
    def extract(self, html: bytes, *, url: str) -> ExtractedContent | None:
        # API and extraction switches:
        # https://trafilatura.readthedocs.io/en/latest/corefunctions.html
        document = trafilatura.bare_extraction(
            html,
            url=url,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
            deduplicate=True,
        )
        if not isinstance(document, Document):
            return None
        title = document.title
        if not title:
            page_title = BeautifulSoup(html, "lxml").title
            title = page_title.get_text(" ", strip=True) if page_title is not None else None
        return _useful(title, document.text)


class BeautifulSoupExtractor:
    def extract(self, html: bytes, *, url: str) -> ExtractedContent | None:
        del url
        soup = BeautifulSoup(html, "lxml")
        for unwanted in soup.select("script, style, noscript, nav, footer, aside, form, svg"):
            unwanted.decompose()
        main = soup.select_one("article, main, [role='main']") or soup.body
        if main is None:
            return None
        heading = main.find("h1")
        page_title = soup.title
        title = heading.get_text(" ", strip=True) if heading is not None else None
        if not title and page_title is not None:
            title = page_title.get_text(" ", strip=True)
        # Text projection API:
        # https://beautiful-soup-4.readthedocs.io/en/latest/#get-text
        return _useful(title, main.get_text(" ", strip=True))


class ExtractionPipeline:
    def __init__(
        self,
        *,
        primary: ContentExtractor | None = None,
        fallback: ContentExtractor | None = None,
    ) -> None:
        self._primary = primary or TrafilaturaExtractor()
        self._fallback = fallback or BeautifulSoupExtractor()

    def extract(self, html: bytes, *, url: str) -> ExtractionResult:
        diagnostics: list[str] = []
        try:
            primary = self._primary.extract(html, url=url)
        except Exception as exc:
            diagnostics.append(f"primary_extractor_error:{type(exc).__name__}")
        else:
            if primary is not None:
                return ExtractionResult(
                    ExtractionStatus.SUCCESS,
                    ExtractorName.TRAFILATURA,
                    primary.title,
                    primary.text,
                    (),
                )
            diagnostics.append("primary_extractor_returned_no_content")

        try:
            fallback = self._fallback.extract(html, url=url)
        except Exception as exc:
            diagnostics.append(f"fallback_extractor_error:{type(exc).__name__}")
        else:
            if fallback is not None:
                return ExtractionResult(
                    ExtractionStatus.PARTIAL,
                    ExtractorName.BEAUTIFULSOUP,
                    fallback.title,
                    fallback.text,
                    tuple(diagnostics),
                )
            diagnostics.append("fallback_extractor_returned_no_content")

        return ExtractionResult(
            ExtractionStatus.FAILED,
            None,
            None,
            None,
            tuple(diagnostics),
        )
