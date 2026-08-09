from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from footballpulse_article_service.application.ingest_article import (
    ArticleIngestionService,
    ArticleProcessingResult,
    CreateArticleVersion,
    ProcessingDisposition,
    RecordUnchangedArticle,
)
from footballpulse_article_service.domain.article import ExistingArticleVersion
from footballpulse_article_service.domain.duplicate import DuplicateCandidate, DuplicateType
from footballpulse_event_contracts.article import ArticleDiscoveredEvent
from footballpulse_fetch_artifacts.filesystem import (
    ArtifactMetadata,
    ArtifactProjection,
    FetchArtifact,
)

EVENT_FIXTURE = (
    Path(__file__).parents[3]
    / "tests"
    / "contract"
    / "fixtures"
    / "article_discovered_v1.valid.json"
)
NOW = datetime(2026, 8, 1, 0, 3, tzinfo=UTC)


class FakeArtifactReader:
    def __init__(self, artifact: FetchArtifact) -> None:
        self.artifact = artifact
        self.read_count = 0

    def read(self, artifact_id: UUID) -> FetchArtifact:
        del artifact_id
        self.read_count += 1
        return self.artifact


class FakeArticleRepository:
    def __init__(self) -> None:
        self.processed: dict[UUID, ArticleProcessingResult] = {}
        self.latest: ExistingArticleVersion | None = None
        self.created_commands: list[object] = []
        self.unchanged_commands: list[object] = []
        self.duplicate_candidates: list[DuplicateCandidate] = []

    def find_processed(self, event_id: UUID) -> ArticleProcessingResult | None:
        return self.processed.get(event_id)

    def find_latest(self, canonical_url: str) -> ExistingArticleVersion | None:
        del canonical_url
        return self.latest

    def find_duplicate_candidates(
        self,
        *,
        content_hash: str,
        collected_at: datetime,
        exclude_article_id: UUID,
        limit: int,
    ) -> list[DuplicateCandidate]:
        del content_hash, collected_at, exclude_article_id
        return self.duplicate_candidates[:limit]

    def persist_created(self, command: CreateArticleVersion) -> ArticleProcessingResult:
        self.created_commands.append(command)
        result = ArticleProcessingResult(
            ProcessingDisposition.CREATED,
            command.article_id,
            command.article_version_id,
            command.outbox_event.event_id,
        )
        self.processed[command.consumed_event_id] = result
        self.latest = ExistingArticleVersion(
            command.article_id,
            command.article_version_id,
            command.version,
            command.content_hash,
        )
        return result

    def persist_unchanged(self, command: RecordUnchangedArticle) -> ArticleProcessingResult:
        self.unchanged_commands.append(command)
        result = ArticleProcessingResult(
            ProcessingDisposition.UNCHANGED,
            command.article_id,
            command.article_version_id,
            None,
        )
        self.processed[command.consumed_event_id] = result
        return result


def _event(*, event_id: str | None = None) -> ArticleDiscoveredEvent:
    document = json.loads(EVENT_FIXTURE.read_text())
    if event_id is not None:
        document["event_id"] = event_id
    document["payload"]["content_length"] = len(b"<html>raw evidence</html>")
    return ArticleDiscoveredEvent.model_validate(document)


def _artifact(*, content_type: str = "text/html") -> FetchArtifact:
    content = b"<html>raw evidence</html>"
    return FetchArtifact(
        content,
        ArtifactMetadata(
            content_type=content_type,
            etag='"v1"',
            last_modified="Fri, 01 Aug 2026 00:00:00 GMT",
            content_length=len(content),
            content_sha256="raw-hash-validated-by-store",
        ),
        ArtifactProjection(
            title="Real Madrid open contract talks",
            cleaned_text="Real Madrid opened contract talks with Vinícius Júnior.",
            status="SUCCESS",
            extractor="TRAFILATURA",
            diagnostics=(),
        ),
    )


def test_creates_first_immutable_version_and_cleaned_outbox_event() -> None:
    reader = FakeArtifactReader(_artifact())
    repository = FakeArticleRepository()
    service = ArticleIngestionService(repository=repository, artifacts=reader, clock=lambda: NOW)

    result = service.handle(_event())

    assert result.disposition is ProcessingDisposition.CREATED
    command = repository.created_commands[0]
    assert command.version == 1
    assert command.previous_version_id is None
    assert command.raw_html == b"<html>raw evidence</html>"
    assert command.cleaned_content.endswith("Vinícius Júnior.")
    assert command.etag == '"v1"'
    assert command.outbox_event.event_type == "article.cleaned"
    assert command.outbox_event.causation_id == _event().event_id
    assert command.outbox_event.payload.duplicate_type == "NONE"


def test_new_event_with_unchanged_content_records_observation_without_outbox() -> None:
    reader = FakeArtifactReader(_artifact())
    repository = FakeArticleRepository()
    service = ArticleIngestionService(repository=repository, artifacts=reader, clock=lambda: NOW)
    first = service.handle(_event())

    second = service.handle(_event(event_id="018f8b45-b634-7c81-a47d-9a7c2f3c2199"))

    assert first.disposition is ProcessingDisposition.CREATED
    assert second.disposition is ProcessingDisposition.UNCHANGED
    assert len(repository.created_commands) == 1
    assert len(repository.unchanged_commands) == 1


def test_replayed_event_returns_before_reading_artifact() -> None:
    reader = FakeArtifactReader(_artifact())
    repository = FakeArticleRepository()
    event = _event()
    repository.processed[event.event_id] = ArticleProcessingResult(
        ProcessingDisposition.CREATED,
        UUID("018f8b45-b634-7c81-a47d-9a7c2f3c4101"),
        UUID("018f8b45-b634-7c81-a47d-9a7c2f3c4201"),
        UUID("018f8b45-b634-7c81-a47d-9a7c2f3c4301"),
    )
    service = ArticleIngestionService(repository=repository, artifacts=reader, clock=lambda: NOW)

    result = service.handle(event)

    assert result.disposition is ProcessingDisposition.REPLAY
    assert reader.read_count == 0


def test_rejects_artifact_metadata_that_does_not_match_event() -> None:
    reader = FakeArtifactReader(_artifact(content_type="application/xhtml+xml"))
    repository = FakeArticleRepository()
    service = ArticleIngestionService(repository=repository, artifacts=reader, clock=lambda: NOW)

    with pytest.raises(ValueError, match="content type"):
        service.handle(_event())

    assert repository.created_commands == []


def test_exact_duplicate_is_linked_in_cleaned_event_and_stops_ai() -> None:
    reader = FakeArtifactReader(_artifact())
    repository = FakeArticleRepository()
    repository.duplicate_candidates = [
        DuplicateCandidate(
            article_id=UUID("018f8b45-b634-7c81-a47d-9a7c2f3c6101"),
            article_version_id=UUID("018f8b45-b634-7c81-a47d-9a7c2f3c6201"),
            title="Syndicated title",
            cleaned_content="Real Madrid opened contract talks with Vinícius Júnior.",
            content_hash=("6400178b7d92a1e41720996b4023ca505e51d2ce65646524fe5a1fd2d37f2814"),
            collected_at=NOW - timedelta(hours=1),
        )
    ]
    service = ArticleIngestionService(repository=repository, artifacts=reader, clock=lambda: NOW)

    service.handle(_event())

    command = repository.created_commands[0]
    assert command.duplicate.duplicate_type is DuplicateType.EXACT
    assert command.duplicate.continue_to_ai is False
    assert command.outbox_event.payload.duplicate_type == "EXACT"
    assert (
        command.outbox_event.payload.duplicate_of_article_version_id
        == repository.duplicate_candidates[0].article_version_id
    )
