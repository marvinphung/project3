from __future__ import annotations

from footballpulse_crawler_service.extraction.extractors import (
    ExtractionPipeline,
    ExtractionResult,
    ExtractionStatus,
)
from footballpulse_crawler_service.extraction.normalization import normalize_article_text


class ArticleContentProcessor:
    def __init__(self, *, extraction: ExtractionPipeline | None = None) -> None:
        self._extraction = extraction or ExtractionPipeline()

    def process(self, html: bytes, *, url: str) -> ExtractionResult:
        extracted = self._extraction.extract(html, url=url)
        if extracted.text is None:
            return extracted

        text = normalize_article_text(extracted.text)
        if not text:
            return ExtractionResult(
                ExtractionStatus.FAILED,
                None,
                None,
                None,
                (*extracted.diagnostics, "normalization_returned_no_content"),
            )
        title = normalize_article_text(extracted.title) if extracted.title else None
        return ExtractionResult(
            extracted.status,
            extracted.extractor,
            title or None,
            text,
            extracted.diagnostics,
        )
