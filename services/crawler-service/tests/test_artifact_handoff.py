from __future__ import annotations

from pathlib import Path
from uuid import UUID

from footballpulse_crawler_service.extraction.artifact_handoff import ArticleArtifactHandoff
from footballpulse_crawler_service.extraction.extractors import (
    ExtractionResult,
    ExtractionStatus,
    ExtractorName,
)
from footballpulse_crawler_service.extraction.service import ExtractedArticle
from footballpulse_fetch_artifacts.filesystem import FilesystemArtifactStore

ARTIFACT_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c2106")


def test_persists_raw_and_cleaned_article_handoff(tmp_path: Path) -> None:
    store = FilesystemArtifactStore(tmp_path)
    handoff = ArticleArtifactHandoff(store=store)
    article = ExtractedArticle(
        source_key="trusted-a",
        requested_url="https://trusted-a.test/story?utm_source=rss",
        final_url="https://trusted-a.test/story",
        content_type="text/html",
        etag='"article-v1"',
        last_modified="Sun, 09 Aug 2026 00:00:00 GMT",
        raw_html=b"<html>raw evidence</html>",
        extraction=ExtractionResult(
            ExtractionStatus.SUCCESS,
            ExtractorName.TRAFILATURA,
            "Transfer update",
            "Arsenal submitted a €180m offer.",
            (),
        ),
    )

    metadata = handoff.persist(ARTIFACT_ID, article)
    loaded = store.read(ARTIFACT_ID)

    assert metadata.content_length == len(article.raw_html)
    assert loaded.content == article.raw_html
    assert loaded.metadata.etag == '"article-v1"'
    assert loaded.projection.cleaned_text == "Arsenal submitted a €180m offer."
