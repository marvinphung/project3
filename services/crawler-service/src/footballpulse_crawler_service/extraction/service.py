from __future__ import annotations

from dataclasses import dataclass

from footballpulse_crawler_service.discovery.runner import DiscoveryJob
from footballpulse_crawler_service.extraction.extractors import ExtractionResult
from footballpulse_crawler_service.extraction.fetcher import HtmlFetcher
from footballpulse_crawler_service.extraction.processor import ArticleContentProcessor


@dataclass(frozen=True, slots=True)
class ExtractedArticle:
    source_key: str
    requested_url: str
    final_url: str
    content_type: str
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
        fetched = await self._fetcher.fetch(
            job.url,
            allowed_domains=job.allowed_domains,
        )
        extraction = self._processor.process(fetched.content, url=fetched.final_url)
        return ExtractedArticle(
            source_key=job.key,
            requested_url=job.url,
            final_url=fetched.final_url,
            content_type=fetched.content_type,
            raw_html=fetched.content,
            extraction=extraction,
        )
