from __future__ import annotations

from uuid import UUID

from footballpulse_fetch_artifacts.filesystem import (
    ArtifactMetadata,
    ArtifactProjection,
    FilesystemArtifactStore,
)

from footballpulse_crawler_service.extraction.service import ExtractedArticle


class ArticleArtifactHandoff:
    def __init__(self, *, store: FilesystemArtifactStore) -> None:
        self._store = store

    def persist(self, artifact_id: UUID, article: ExtractedArticle) -> ArtifactMetadata:
        extraction = article.extraction
        return self._store.put(
            artifact_id,
            article.raw_html,
            metadata=ArtifactMetadata(
                content_type=article.content_type,
                etag=article.etag,
                last_modified=article.last_modified,
            ),
            projection=ArtifactProjection(
                title=extraction.title,
                cleaned_text=extraction.text,
                status=extraction.status.value,
                extractor=extraction.extractor.value if extraction.extractor else None,
                diagnostics=extraction.diagnostics,
            ),
        )
