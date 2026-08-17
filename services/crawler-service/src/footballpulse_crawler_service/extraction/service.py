from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from footballpulse_runtime_config import log_event

from footballpulse_crawler_service.discovery.runner import DiscoveryJob
from footballpulse_crawler_service.extraction.extractors import ExtractionResult
from footballpulse_crawler_service.extraction.fetcher import HtmlFetcher
from footballpulse_crawler_service.extraction.processor import ArticleContentProcessor

LOGGER = logging.getLogger("footballpulse.crawler.extraction")


@dataclass(frozen=True, slots=True)
class ExtractedArticle:
    source_key: str
    requested_url: str
    final_url: str
    content_type: str
    etag: str | None
    last_modified: str | None
    raw_html: bytes
    extraction: ExtractionResult


class HtmlExtractionService:
    def __init__(
        self,
        *,
        fetcher: HtmlFetcher,
        processor: ArticleContentProcessor | None = None,
    ) -> None:
        self._fetcher = fetcher
        self._processor = processor or ArticleContentProcessor()

    async def fetch_and_extract(self, job: DiscoveryJob) -> ExtractedArticle:
        started = time.monotonic()
        log_event(LOGGER, "article_fetch_started", source_key=job.key, url=job.url)
        try:
            fetched = await self._fetcher.fetch(
                job.url,
                allowed_domains=job.allowed_domains,
            )
            extraction = self._processor.process(fetched.content, url=fetched.final_url)
        except Exception as error:
            log_event(
                LOGGER,
                "article_fetch_failed",
                level=logging.ERROR,
                error=error,
                source_key=job.key,
                url=job.url,
                duration_ms=round((time.monotonic() - started) * 1000),
            )
            raise
        log_event(
            LOGGER,
            "article_extraction_completed",
            source_key=job.key,
            final_url=fetched.final_url,
            content_type=fetched.content_type,
            response_bytes=len(fetched.content),
            extraction_status=extraction.status.value,
            extractor=extraction.extractor,
            text_chars=len(extraction.text or ""),
            duration_ms=round((time.monotonic() - started) * 1000),
        )
        return ExtractedArticle(
            source_key=job.key,
            requested_url=job.url,
            final_url=fetched.final_url,
            content_type=fetched.content_type,
            etag=fetched.etag,
            last_modified=fetched.last_modified,
            raw_html=fetched.content,
            extraction=extraction,
        )
