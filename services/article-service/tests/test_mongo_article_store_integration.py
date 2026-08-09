from __future__ import annotations

import json
import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4, uuid5

import pytest
from footballpulse_article_service.application.ingest_article import (
    ArticleIngestionService,
    ProcessingDisposition,
)
from footballpulse_article_service.messaging.outbox import OutboxPublisher, PublishBatchResult
from footballpulse_article_service.persistence.mongo_article_store import MongoArticleStore
from footballpulse_article_service.persistence.mongo_indexes import bootstrap_indexes
from footballpulse_crawler_service.discovery.rss import parse_rss
from footballpulse_crawler_service.extraction.artifact_handoff import ArticleArtifactHandoff
from footballpulse_crawler_service.extraction.processor import ArticleContentProcessor
from footballpulse_crawler_service.extraction.service import ExtractedArticle
from footballpulse_event_contracts.article import ArticleDiscoveredEvent, ArticleDiscoveredPayload
from footballpulse_fetch_artifacts.filesystem import (
    ArtifactMetadata,
    ArtifactProjection,
    FilesystemArtifactStore,
)
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

ROOT = Path(__file__).parents[3]
PHASE_2_NAMESPACE = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c7999")


@pytest.fixture
def mongo_database() -> Iterator[Database[dict[str, object]]]:
    mongo_url = os.getenv(
        "FOOTBALLPULSE_MONGODB_URL",
        "mongodb://127.0.0.1:27017/?directConnection=true",
    )
    database_name = f"footballpulse_article_test_{uuid4().hex}"
    with MongoClient[dict[str, object]](mongo_url) as client:
        database = client[database_name]
        yield database
        client.drop_database(database_name)


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("FOOTBALLPULSE_RUN_MONGO_INTEGRATION") != "1",
    reason="set FOOTBALLPULSE_RUN_MONGO_INTEGRATION=1 with MongoDB replica set running",
)
def test_atomic_article_write_is_idempotent_and_rolls_back_on_outbox_conflict(
    mongo_database: Database[dict[str, object]],
) -> None:
    bootstrap_indexes(mongo_database)
    bootstrap_indexes(mongo_database)
    store = MongoArticleStore(mongo_database)
    article = {
        "_id": "article-version-1",
        "canonical_article_id": "article-1",
        "version": 1,
        "cleaned_content": "Arsenal submitted a bid.",
    }
    outbox_event = {
        "_id": "outbox-1",
        "event_id": "article-cleaned-1",
        "event_type": "article.cleaned",
        "status": "PENDING",
    }

    first = store.store_article_once(
        consumed_event_id="article-discovered-1",
        article_document=article,
        outbox_document=outbox_event,
    )
    replay = store.store_article_once(
        consumed_event_id="article-discovered-1",
        article_document=article,
        outbox_document=outbox_event,
    )

    assert first.created is True
    assert replay == first.as_replay()
    assert mongo_database.source_articles.count_documents({}) == 1
    assert mongo_database.processed_events.count_documents({}) == 1
    assert mongo_database.outbox.count_documents({}) == 1
    stored_outbox = mongo_database.outbox.find_one({"event_id": "article-cleaned-1"})
    assert stored_outbox is not None
    assert stored_outbox["available_at"] == stored_outbox["created_at"]
    assert stored_outbox["publish_attempts"] == 0

    with pytest.raises(DuplicateKeyError):
        store.store_article_once(
            consumed_event_id="article-discovered-2",
            article_document={
                "_id": "article-version-2",
                "canonical_article_id": "article-2",
                "version": 1,
            },
            outbox_document={
                "_id": "outbox-conflict",
                "event_id": "article-cleaned-1",
                "event_type": "article.cleaned",
                "status": "PENDING",
            },
        )

    assert mongo_database.source_articles.count_documents({"_id": "article-version-2"}) == 0
    assert (
        mongo_database.processed_events.count_documents({"event_id": "article-discovered-2"}) == 0
    )


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("FOOTBALLPULSE_RUN_MONGO_INTEGRATION") != "1",
    reason="set FOOTBALLPULSE_RUN_MONGO_INTEGRATION=1 with MongoDB replica set running",
)
def test_version_ingestion_distinguishes_replay_unchanged_and_changed(
    mongo_database: Database[dict[str, object]],
    tmp_path: Path,
) -> None:
    bootstrap_indexes(mongo_database)
    artifacts = FilesystemArtifactStore(tmp_path)
    repository = MongoArticleStore(mongo_database)
    now = datetime(2026, 8, 1, 0, 3, tzinfo=UTC)
    service = ArticleIngestionService(repository=repository, artifacts=artifacts, clock=lambda: now)
    source_id = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c2104")
    batch_id = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c2105")

    def event(event_id: UUID, artifact_id: UUID, raw: bytes) -> ArticleDiscoveredEvent:
        return ArticleDiscoveredEvent(
            event_id=event_id,
            event_type="article.discovered",
            event_version=1,
            occurred_at=now,
            producer="crawler-service",
            correlation_id=batch_id,
            causation_id=None,
            aggregate_type="source_article",
            aggregate_id=event_id,
            idempotency_key=f"fixture:{event_id}",
            payload=ArticleDiscoveredPayload(
                source_id=source_id,
                batch_id=batch_id,
                canonical_url="https://news.example.com/story?utm_source=rss",
                rss_guid=str(event_id),
                rss_title="Transfer update",
                rss_published_at=now,
                fetched_at=now,
                fetch_artifact_id=artifact_id,
                http_status=200,
                content_type="text/html",
                content_length=len(raw),
            ),
        )

    inputs = [
        (
            UUID("018f8b45-b634-7c81-a47d-9a7c2f3c5101"),
            UUID("018f8b45-b634-7c81-a47d-9a7c2f3c5201"),
            b"<html>version one</html>",
            "Real Madrid opened contract talks.",
        ),
        (
            UUID("018f8b45-b634-7c81-a47d-9a7c2f3c5102"),
            UUID("018f8b45-b634-7c81-a47d-9a7c2f3c5202"),
            b"<html>same report fetched later</html>",
            "Real Madrid opened contract talks.",
        ),
        (
            UUID("018f8b45-b634-7c81-a47d-9a7c2f3c5103"),
            UUID("018f8b45-b634-7c81-a47d-9a7c2f3c5203"),
            b"<html>version two</html>",
            "Real Madrid rejected the offer.",
        ),
    ]
    events: list[ArticleDiscoveredEvent] = []
    for event_id, artifact_id, raw, cleaned in inputs:
        artifacts.put(
            artifact_id,
            raw,
            metadata=ArtifactMetadata(content_type="text/html"),
            projection=ArtifactProjection(
                title="Transfer update",
                cleaned_text=cleaned,
                status="SUCCESS",
                extractor="TRAFILATURA",
                diagnostics=(),
            ),
        )
        events.append(event(event_id, artifact_id, raw))

    first = service.handle(events[0])
    replay = service.handle(events[0])
    unchanged = service.handle(events[1])
    changed = service.handle(events[2])

    assert first.disposition is ProcessingDisposition.CREATED
    assert replay.disposition is ProcessingDisposition.REPLAY
    assert unchanged.disposition is ProcessingDisposition.UNCHANGED
    assert changed.disposition is ProcessingDisposition.CREATED
    assert mongo_database.source_articles.count_documents({}) == 2
    assert mongo_database.processed_events.count_documents({}) == 3
    assert mongo_database.outbox.count_documents({}) == 2
    versions = list(mongo_database.source_articles.find().sort("version", 1))
    assert versions[0]["raw_html"] == inputs[0][2]
    assert versions[1]["previous_version_id"] == versions[0]["article_version_id"]
    unchanged_marker = mongo_database.processed_events.find_one(
        {"event_id": str(events[1].event_id)}
    )
    assert unchanged_marker is not None
    assert unchanged_marker["duplicate_type"] == "URL"
    assert unchanged_marker["duplicate_reason"] == "same_canonical_url_and_content_hash"

    class RecordingKafka:
        def __init__(self) -> None:
            self.values: list[bytes] = []

        def publish(self, *, topic: str, key: str, value: bytes) -> None:
            assert topic == "article.cleaned.v1"
            assert key
            self.values.append(value)

    kafka = RecordingKafka()
    publish_result = OutboxPublisher(
        repository=repository,
        kafka=kafka,
        clock=lambda: now,
    ).publish_pending(limit=10)

    assert publish_result == PublishBatchResult(attempted=2, published=2, failed=0)
    assert len(kafka.values) == 2
    assert mongo_database.outbox.count_documents({"status": "PUBLISHED"}) == 2


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("FOOTBALLPULSE_RUN_MONGO_INTEGRATION") != "1",
    reason="set FOOTBALLPULSE_RUN_MONGO_INTEGRATION=1 with MongoDB replica set running",
)
def test_duplicate_matrix_persists_auditable_links_and_outbox_decisions(
    mongo_database: Database[dict[str, object]],
    tmp_path: Path,
) -> None:
    bootstrap_indexes(mongo_database)
    artifacts = FilesystemArtifactStore(tmp_path)
    repository = MongoArticleStore(mongo_database)
    base_time = datetime(2026, 8, 1, 0, 0, tzinfo=UTC)
    source_id = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c7101")
    batch_id = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c7102")
    service = ArticleIngestionService(
        repository=repository,
        artifacts=artifacts,
        clock=lambda: base_time + timedelta(hours=1),
    )
    offer_title = "Arsenal submit €180m Vinicius offer"
    offer_text = (
        "Arsenal send €180m offer to Real Madrid for Vinícius Júnior Arsenal have "
        "submitted a formal offer worth €180 million to Real Madrid for Vinícius Júnior. "
        "Real Madrid have not yet responded to the proposal."
    )
    cases = (
        ("primary", offer_title, offer_text),
        ("exact", "Syndicated transfer report", offer_text),
        (
            "near",
            "Gunners lodge major Vinicius proposal",
            "Gunners lodge major proposal for Real star Arsenal, also known as the Gunners, "
            "lodged an offer valued at €180m for Real Madrid winger Vinícius Júnior. The "
            "Spanish club is considering the bid.",
        ),
        (
            "injury",
            "Vinicius ruled out with hamstring injury",
            "Vinícius Júnior suffers hamstring injury Real Madrid coach Xabi Alonso said "
            "Vini Jr will miss the La Liga opener with a hamstring injury.",
        ),
        (
            "match",
            "Real Madrid beat Arsenal 2-1",
            "Real Madrid beat Arsenal in friendly Real Madrid defeated Arsenal 2-1 after a "
            "late winner in a pre-season match.",
        ),
    )

    for offset, (slug, title, cleaned_text) in enumerate(cases):
        fetched_at = base_time + timedelta(minutes=offset)
        event_id = UUID(f"018f8b45-b634-7c81-a47d-9a7c2f3c72{offset:02d}")
        artifact_id = UUID(f"018f8b45-b634-7c81-a47d-9a7c2f3c73{offset:02d}")
        raw = f"<html>{slug}</html>".encode()
        artifacts.put(
            artifact_id,
            raw,
            metadata=ArtifactMetadata(content_type="text/html"),
            projection=ArtifactProjection(
                title=title,
                cleaned_text=cleaned_text,
                status="SUCCESS",
                extractor="TRAFILATURA",
                diagnostics=(),
            ),
        )
        event = ArticleDiscoveredEvent(
            event_id=event_id,
            event_type="article.discovered",
            event_version=1,
            occurred_at=fetched_at,
            producer="crawler-service",
            correlation_id=batch_id,
            causation_id=None,
            aggregate_type="source_article",
            aggregate_id=event_id,
            idempotency_key=f"fixture:{event_id}",
            payload=ArticleDiscoveredPayload(
                source_id=source_id,
                batch_id=batch_id,
                canonical_url=f"https://news.example.com/{slug}?utm_source=rss",
                rss_guid=str(event_id),
                rss_title=title,
                rss_published_at=fetched_at,
                fetched_at=fetched_at,
                fetch_artifact_id=artifact_id,
                http_status=200,
                content_type="text/html",
                content_length=len(raw),
            ),
        )
        service.handle(event)

    articles = {
        str(document["canonical_url"]).rsplit("/", maxsplit=1)[-1]: document
        for document in mongo_database.source_articles.find()
    }
    assert articles["primary"]["duplicate_type"] == "NONE"
    assert articles["exact"]["duplicate_type"] == "EXACT"
    assert articles["near"]["duplicate_type"] == "NEAR"
    assert articles["injury"]["duplicate_type"] == "NONE"
    assert articles["match"]["duplicate_type"] == "NONE"

    links = list(mongo_database.duplicate_links.find().sort("duplicate_type", 1))
    assert [link["duplicate_type"] for link in links] == ["EXACT", "NEAR"]
    for link in links:
        assert link["primary_article_version_id"] == articles["primary"]["article_version_id"]
        assert link["reason"]
        assert link["threshold"] == 0.65
        assert set(link["components"]) == {
            "title_similarity",
            "content_similarity",
            "time_similarity",
        }

    outbox_types = {
        document["event"]["payload"]["duplicate_type"] for document in mongo_database.outbox.find()
    }
    assert outbox_types == {"NONE", "EXACT", "NEAR"}


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("FOOTBALLPULSE_RUN_MONGO_INTEGRATION") != "1",
    reason="set FOOTBALLPULSE_RUN_MONGO_INTEGRATION=1 with MongoDB replica set running",
)
def test_phase_2_fixture_rss_reaches_immutable_mongo_evidence_and_outbox(
    mongo_database: Database[dict[str, object]],
    tmp_path: Path,
) -> None:
    catalog = json.loads((ROOT / "tests/fixtures/mock-news/catalog.json").read_text())
    articles_by_url = {
        article["url"]: article for article in catalog["articles"] if article["fixture"] is not None
    }
    feed = parse_rss(
        (ROOT / "tests/fixtures/mock-news/rss/trusted-transfer.xml").read_bytes(),
        allowed_domains=("trusted-a.test", "trusted-b.test"),
        max_entries=20,
    )
    assert len(feed.entries) == 7

    bootstrap_indexes(mongo_database)
    artifact_store = FilesystemArtifactStore(tmp_path)
    handoff = ArticleArtifactHandoff(store=artifact_store)
    processor = ArticleContentProcessor()
    repository = MongoArticleStore(mongo_database)
    batch_id = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c7901")
    service = ArticleIngestionService(
        repository=repository,
        artifacts=artifact_store,
        clock=lambda: datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
    )

    for entry in feed.entries:
        fixture = articles_by_url[entry.url]
        event_id = UUID(fixture["id"])
        artifact_id = uuid5(PHASE_2_NAMESPACE, f"artifact:{event_id}")
        raw_html = (ROOT / fixture["fixture"]).read_bytes()
        extraction = processor.process(raw_html, url=entry.url)
        metadata = handoff.persist(
            artifact_id,
            ExtractedArticle(
                source_key=str(fixture["source_id"]),
                requested_url=entry.url,
                final_url=entry.url,
                content_type="text/html",
                etag=None,
                last_modified=None,
                raw_html=raw_html,
                extraction=extraction,
            ),
        )
        fetched_at = datetime.fromisoformat(fixture["discovered_at"])
        service.handle(
            ArticleDiscoveredEvent(
                event_id=event_id,
                event_type="article.discovered",
                event_version=1,
                occurred_at=fetched_at,
                producer="crawler-service",
                correlation_id=batch_id,
                causation_id=None,
                aggregate_type="source_article",
                aggregate_id=event_id,
                idempotency_key=f"phase-2:{event_id}",
                payload=ArticleDiscoveredPayload(
                    source_id=UUID(fixture["source_id"]),
                    batch_id=batch_id,
                    canonical_url=entry.url,
                    rss_guid=entry.guid,
                    rss_title=entry.title,
                    rss_published_at=entry.published_at,
                    fetched_at=fetched_at,
                    fetch_artifact_id=artifact_id,
                    http_status=200,
                    content_type="text/html",
                    content_length=metadata.content_length,
                ),
            )
        )

    assert mongo_database.processed_events.count_documents({}) == 7
    assert mongo_database.source_articles.count_documents({}) == 6
    assert mongo_database.outbox.count_documents({}) == 6
    assert mongo_database.processed_events.count_documents({"duplicate_type": "URL"}) == 1

    stored_types = {
        document["duplicate_type"]
        for document in mongo_database.source_articles.find({}, {"duplicate_type": 1})
    }
    assert stored_types == {"NONE", "EXACT", "NEAR"}
    link_types = [
        document["duplicate_type"]
        for document in mongo_database.duplicate_links.find().sort("duplicate_type", 1)
    ]
    assert link_types == ["EXACT", "NEAR", "NEAR"]
