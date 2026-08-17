from __future__ import annotations

import hashlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID, uuid5

from footballpulse_event_contracts.article import (
    ArticleCleanedEvent,
    ArticleCleanedPayload,
    ArticleDiscoveredEvent,
)
from footballpulse_fetch_artifacts.filesystem import FetchArtifact
from footballpulse_runtime_config import bind_log_context, log_event
from pydantic import HttpUrl

from footballpulse_article_service.domain.article import (
    ExistingArticleVersion,
    VersionDecisionKind,
    canonicalize_article_url,
    decide_article_version,
)
from footballpulse_article_service.domain.duplicate import (
    DuplicateCandidate,
    DuplicateDecision,
    DuplicatePolicy,
)

_OUTBOX_NAMESPACE = UUID("4f0f31e2-9c16-47f5-8035-f6b598a2c98e")
LOGGER = logging.getLogger("footballpulse.article.ingestion")


class ProcessingDisposition(StrEnum):
    CREATED = "CREATED"
    UNCHANGED = "UNCHANGED"
    REPLAY = "REPLAY"


@dataclass(frozen=True, slots=True)
class ArticleProcessingResult:
    disposition: ProcessingDisposition
    article_id: UUID
    article_version_id: UUID
    outbox_event_id: UUID | None

    def as_replay(self) -> ArticleProcessingResult:
        return replace(self, disposition=ProcessingDisposition.REPLAY)


@dataclass(frozen=True, slots=True)
class CreateArticleVersion:
    consumed_event_id: UUID
    fetch_artifact_id: UUID
    source_id: UUID
    batch_id: UUID
    article_id: UUID
    article_version_id: UUID
    mongo_document_id: str
    canonical_url: str
    version: int
    previous_version_id: UUID | None
    title: str
    cleaned_content: str
    content_hash: str
    raw_html: bytes
    raw_content_hash: str
    content_type: str
    etag: str | None
    last_modified: str | None
    extraction_status: str
    extractor: str
    extraction_diagnostics: tuple[str, ...]
    rss_guid: str | None
    rss_title: str
    rss_published_at: datetime | None
    fetched_at: datetime
    cleaned_at: datetime
    duplicate: DuplicateDecision
    outbox_event: ArticleCleanedEvent


@dataclass(frozen=True, slots=True)
class RecordUnchangedArticle:
    consumed_event_id: UUID
    article_id: UUID
    article_version_id: UUID
    canonical_url: str
    fetched_at: datetime
    fetch_artifact_id: UUID
    etag: str | None
    last_modified: str | None
    duplicate_reason: str = "same_canonical_url_and_content_hash"


class ArtifactReader(Protocol):
    def read(self, artifact_id: UUID) -> FetchArtifact: ...


class ArticleRepository(Protocol):
    def find_processed(self, event_id: UUID) -> ArticleProcessingResult | None: ...

    def find_latest(self, canonical_url: str) -> ExistingArticleVersion | None: ...

    def find_duplicate_candidates(
        self,
        *,
        content_hash: str,
        collected_at: datetime,
        exclude_article_id: UUID,
        limit: int,
    ) -> list[DuplicateCandidate]: ...

    def persist_created(self, command: CreateArticleVersion) -> ArticleProcessingResult: ...

    def persist_unchanged(self, command: RecordUnchangedArticle) -> ArticleProcessingResult: ...


class ArticleIngestionService:
    def __init__(
        self,
        *,
        repository: ArticleRepository,
        artifacts: ArtifactReader,
        clock: Callable[[], datetime],
        duplicate_policy: DuplicatePolicy | None = None,
    ) -> None:
        self._repository = repository
        self._artifacts = artifacts
        self._clock = clock
        self._duplicate_policy = duplicate_policy or DuplicatePolicy()

    def handle(self, event: ArticleDiscoveredEvent) -> ArticleProcessingResult:
        started = time.monotonic()
        with bind_log_context(
            correlation_id=str(event.correlation_id),
            batch_id=str(event.payload.batch_id),
        ):
            log_event(
                LOGGER,
                "article_ingestion_started",
                event_id=str(event.event_id),
                source_id=str(event.payload.source_id),
            )
            try:
                result = self._handle(event)
            except Exception as error:
                log_event(
                    LOGGER,
                    "article_ingestion_failed",
                    level=logging.ERROR,
                    error=error,
                    event_id=str(event.event_id),
                    duration_ms=round((time.monotonic() - started) * 1000),
                )
                raise
            log_event(
                LOGGER,
                "article_ingestion_completed",
                event_id=str(event.event_id),
                article_id=str(result.article_id),
                article_version_id=str(result.article_version_id),
                disposition=result.disposition.value,
                duration_ms=round((time.monotonic() - started) * 1000),
            )
            return result

    def _handle(self, event: ArticleDiscoveredEvent) -> ArticleProcessingResult:
        replay = self._repository.find_processed(event.event_id)
        if replay is not None:
            return replay.as_replay()

        artifact = self._artifacts.read(event.payload.fetch_artifact_id)
        self._validate_handoff(event, artifact)
        projection = artifact.projection
        if projection.status == "FAILED":
            raise ValueError("failed extraction artifact cannot create an article version")
        if (
            projection.title is None
            or projection.cleaned_text is None
            or projection.extractor is None
        ):
            raise ValueError("article artifact projection is incomplete")

        canonical_url = canonicalize_article_url(str(event.payload.canonical_url))
        latest = self._repository.find_latest(canonical_url)
        decision = decide_article_version(
            canonical_url=canonical_url,
            cleaned_content=projection.cleaned_text,
            latest=latest,
        )
        if decision.kind is VersionDecisionKind.UNCHANGED:
            return self._repository.persist_unchanged(
                RecordUnchangedArticle(
                    consumed_event_id=event.event_id,
                    article_id=decision.article_id,
                    article_version_id=decision.article_version_id,
                    canonical_url=canonical_url,
                    fetched_at=event.payload.fetched_at,
                    fetch_artifact_id=event.payload.fetch_artifact_id,
                    etag=artifact.metadata.etag,
                    last_modified=artifact.metadata.last_modified,
                )
            )

        cleaned_at = self._clock()
        candidates = self._repository.find_duplicate_candidates(
            content_hash=decision.content_hash,
            collected_at=event.payload.fetched_at,
            exclude_article_id=decision.article_id,
            limit=50,
        )
        duplicate = self._duplicate_policy.classify(
            title=projection.title,
            cleaned_content=projection.cleaned_text,
            collected_at=event.payload.fetched_at,
            candidates=candidates,
        )
        mongo_document_id = hashlib.sha256(decision.article_version_id.bytes).hexdigest()[:24]
        outbox_event_id = uuid5(
            _OUTBOX_NAMESPACE, f"article.cleaned.v1:{decision.article_version_id}"
        )
        outbox_event = ArticleCleanedEvent(
            event_id=outbox_event_id,
            event_type="article.cleaned",
            event_version=1,
            occurred_at=cleaned_at,
            producer="article-service",
            correlation_id=event.correlation_id,
            causation_id=event.event_id,
            aggregate_type="article_version",
            aggregate_id=decision.article_version_id,
            idempotency_key=f"article-version:{decision.article_version_id}:cleaned:v1",
            payload=ArticleCleanedPayload(
                source_id=event.payload.source_id,
                article_id=decision.article_id,
                article_version_id=decision.article_version_id,
                canonical_url=HttpUrl(canonical_url),
                title=projection.title,
                content_hash=decision.content_hash,
                language="en",
                cleaned_at=cleaned_at,
                mongo_collection="source_articles",
                mongo_document_id=mongo_document_id,
                duplicate_type=duplicate.duplicate_type.value,
                duplicate_of_article_version_id=duplicate.primary_article_version_id,
            ),
        )
        return self._repository.persist_created(
            CreateArticleVersion(
                consumed_event_id=event.event_id,
                fetch_artifact_id=event.payload.fetch_artifact_id,
                source_id=event.payload.source_id,
                batch_id=event.payload.batch_id,
                article_id=decision.article_id,
                article_version_id=decision.article_version_id,
                mongo_document_id=mongo_document_id,
                canonical_url=canonical_url,
                version=decision.version,
                previous_version_id=decision.previous_version_id,
                title=projection.title,
                cleaned_content=projection.cleaned_text,
                content_hash=decision.content_hash,
                raw_html=artifact.content,
                raw_content_hash=artifact.metadata.content_sha256,
                content_type=artifact.metadata.content_type,
                etag=artifact.metadata.etag,
                last_modified=artifact.metadata.last_modified,
                extraction_status=projection.status,
                extractor=projection.extractor,
                extraction_diagnostics=projection.diagnostics,
                rss_guid=event.payload.rss_guid,
                rss_title=event.payload.rss_title,
                rss_published_at=event.payload.rss_published_at,
                fetched_at=event.payload.fetched_at,
                cleaned_at=cleaned_at,
                duplicate=duplicate,
                outbox_event=outbox_event,
            )
        )

    @staticmethod
    def _validate_handoff(event: ArticleDiscoveredEvent, artifact: FetchArtifact) -> None:
        if artifact.metadata.content_type != event.payload.content_type:
            raise ValueError("artifact content type does not match discovered event")
        if artifact.metadata.content_length != event.payload.content_length:
            raise ValueError("artifact content length does not match discovered event")
