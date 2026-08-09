from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

from pymongo import ReadPreference
from pymongo.client_session import ClientSession
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

from footballpulse_article_service.application.ingest_article import (
    ArticleProcessingResult,
    CreateArticleVersion,
    ProcessingDisposition,
    RecordUnchangedArticle,
)
from footballpulse_article_service.domain.article import ExistingArticleVersion
from footballpulse_article_service.messaging.outbox import OutboxRecord

MongoDocument = dict[str, object]


@dataclass(frozen=True, slots=True)
class ArticleWriteResult:
    article_id: str
    outbox_event_id: str
    created: bool

    def as_replay(self) -> ArticleWriteResult:
        return replace(self, created=False)


class MongoArticleStore:
    def __init__(self, database: Database[MongoDocument]) -> None:
        self._database = database

    def store_article_once(
        self,
        *,
        consumed_event_id: str,
        article_document: Mapping[str, object],
        outbox_document: Mapping[str, object],
    ) -> ArticleWriteResult:
        article = dict(article_document)
        outbox = dict(outbox_document)
        article_id = self._required_string(article, "_id")
        outbox_event_id = self._required_string(outbox, "event_id")

        replay = self._find_replay(consumed_event_id)
        if replay is not None:
            return replay

        def write_transaction(session: ClientSession) -> ArticleWriteResult:
            processed_at = datetime.now(UTC)
            self._database.processed_events.insert_one(
                {
                    "_id": consumed_event_id,
                    "event_id": consumed_event_id,
                    "article_id": article_id,
                    "outbox_event_id": outbox_event_id,
                    "processed_at": processed_at,
                },
                session=session,
            )
            self._database.source_articles.insert_one(article, session=session)
            outbox.setdefault("status", "PENDING")
            outbox.setdefault("created_at", processed_at)
            outbox.setdefault("available_at", processed_at)
            outbox.setdefault("publish_attempts", 0)
            self._database.outbox.insert_one(outbox, session=session)
            return ArticleWriteResult(
                article_id=article_id,
                outbox_event_id=outbox_event_id,
                created=True,
            )

        try:
            with self._database.client.start_session() as session:
                result = session.with_transaction(
                    write_transaction,
                    read_concern=ReadConcern("snapshot"),
                    write_concern=WriteConcern("majority"),
                    read_preference=ReadPreference.PRIMARY,
                )
                if result is None:
                    raise RuntimeError("MongoDB transaction completed without a write result")
                return result
        except DuplicateKeyError:
            replay = self._find_replay(consumed_event_id)
            if replay is not None:
                return replay
            raise

    def find_processed(self, event_id: UUID) -> ArticleProcessingResult | None:
        marker = self._database.processed_events.find_one({"event_id": str(event_id)})
        if marker is None:
            return None
        return self._article_processing_result(marker)

    def find_latest(self, canonical_url: str) -> ExistingArticleVersion | None:
        document = self._database.source_articles.find_one(
            {"canonical_url": canonical_url},
            sort=[("version", -1)],
        )
        if document is None:
            return None
        return ExistingArticleVersion(
            article_id=UUID(self._required_string(document, "canonical_article_id")),
            article_version_id=UUID(self._required_string(document, "article_version_id")),
            version=self._required_int(document, "version"),
            content_hash=self._required_string(document, "content_hash"),
        )

    def persist_created(self, command: CreateArticleVersion) -> ArticleProcessingResult:
        replay = self.find_processed(command.consumed_event_id)
        if replay is not None:
            return replay.as_replay()

        result = ArticleProcessingResult(
            ProcessingDisposition.CREATED,
            command.article_id,
            command.article_version_id,
            command.outbox_event.event_id,
        )
        article_document: MongoDocument = {
            "_id": command.mongo_document_id,
            "canonical_article_id": str(command.article_id),
            "article_version_id": str(command.article_version_id),
            "source_id": str(command.source_id),
            "batch_id": str(command.batch_id),
            "canonical_url": command.canonical_url,
            "version": command.version,
            "previous_version_id": (
                str(command.previous_version_id) if command.previous_version_id else None
            ),
            "title": command.title,
            "raw_html": command.raw_html,
            "raw_content_hash": command.raw_content_hash,
            "cleaned_content": command.cleaned_content,
            "content_hash": command.content_hash,
            "language": "en",
            "content_type": command.content_type,
            "etag": command.etag,
            "last_modified": command.last_modified,
            "extraction_status": command.extraction_status,
            "extractor": command.extractor,
            "extraction_diagnostics": list(command.extraction_diagnostics),
            "rss_guid": command.rss_guid,
            "rss_title": command.rss_title,
            "rss_published_at": command.rss_published_at,
            "collected_at": command.fetched_at,
            "cleaned_at": command.cleaned_at,
        }
        outbox_document: MongoDocument = {
            "_id": str(command.outbox_event.event_id),
            "event_id": str(command.outbox_event.event_id),
            "event_type": "article.cleaned",
            "event_version": 1,
            "topic": "article.cleaned.v1",
            "key": str(command.article_id),
            "event": command.outbox_event.model_dump(mode="json"),
            "status": "PENDING",
            "created_at": command.cleaned_at,
            "available_at": command.cleaned_at,
            "publish_attempts": 0,
        }

        def write_transaction(session: ClientSession) -> ArticleProcessingResult:
            replay_in_transaction = self._find_article_replay(
                command.consumed_event_id,
                session=session,
            )
            if replay_in_transaction is not None:
                return replay_in_transaction.as_replay()
            self._database.processed_events.insert_one(
                self._processed_marker(
                    command.consumed_event_id,
                    result,
                    processed_at=command.cleaned_at,
                    fetch_artifact_id=command.fetch_artifact_id,
                ),
                session=session,
            )
            self._database.source_articles.insert_one(article_document, session=session)
            self._database.outbox.insert_one(outbox_document, session=session)
            return result

        return self._run_transaction(write_transaction)

    def persist_unchanged(self, command: RecordUnchangedArticle) -> ArticleProcessingResult:
        replay = self.find_processed(command.consumed_event_id)
        if replay is not None:
            return replay.as_replay()
        result = ArticleProcessingResult(
            ProcessingDisposition.UNCHANGED,
            command.article_id,
            command.article_version_id,
            None,
        )

        def write_transaction(session: ClientSession) -> ArticleProcessingResult:
            replay_in_transaction = self._find_article_replay(
                command.consumed_event_id,
                session=session,
            )
            if replay_in_transaction is not None:
                return replay_in_transaction.as_replay()
            marker = self._processed_marker(
                command.consumed_event_id,
                result,
                processed_at=command.fetched_at,
                fetch_artifact_id=command.fetch_artifact_id,
            )
            marker.update(
                {
                    "canonical_url": command.canonical_url,
                    "etag": command.etag,
                    "last_modified": command.last_modified,
                }
            )
            self._database.processed_events.insert_one(marker, session=session)
            return result

        return self._run_transaction(write_transaction)

    def list_pending_outbox(self, *, limit: int, now: datetime) -> list[OutboxRecord]:
        if not 1 <= limit <= 100:
            raise ValueError("outbox query limit must be between 1 and 100")
        documents = (
            self._database.outbox.find(
                {"status": "PENDING", "available_at": {"$lte": now}},
            )
            .sort("created_at", 1)
            .limit(limit)
        )
        records: list[OutboxRecord] = []
        for document in documents:
            event = document.get("event")
            if not isinstance(event, Mapping):
                raise ValueError("outbox event must be a document")
            records.append(
                OutboxRecord(
                    event_id=UUID(self._required_string(document, "event_id")),
                    topic=self._required_string(document, "topic"),
                    key=self._required_string(document, "key"),
                    event=event,
                )
            )
        return records

    def mark_outbox_published(self, event_id: UUID, *, published_at: datetime) -> None:
        result = self._database.outbox.update_one(
            {"event_id": str(event_id), "status": "PENDING"},
            {"$set": {"status": "PUBLISHED", "published_at": published_at}},
        )
        if result.matched_count:
            return
        existing = self._database.outbox.find_one(
            {"event_id": str(event_id)},
            {"status": 1},
        )
        if existing is None or existing.get("status") != "PUBLISHED":
            raise ValueError("pending outbox event was not found")

    def record_outbox_failure(self, event_id: UUID, *, failed_at: datetime) -> None:
        result = self._database.outbox.update_one(
            {"event_id": str(event_id), "status": "PENDING"},
            {
                "$inc": {"publish_attempts": 1},
                "$set": {
                    "last_failed_at": failed_at,
                    "available_at": failed_at + timedelta(seconds=30),
                },
            },
        )
        if result.matched_count != 1:
            raise ValueError("pending outbox event was not found")

    def _run_transaction(
        self,
        callback: Callable[[ClientSession], ArticleProcessingResult],
    ) -> ArticleProcessingResult:
        with self._database.client.start_session() as session:
            result = session.with_transaction(
                callback,
                read_concern=ReadConcern("snapshot"),
                write_concern=WriteConcern("majority"),
                read_preference=ReadPreference.PRIMARY,
            )
            if result is None:
                raise RuntimeError("MongoDB transaction completed without a write result")
            return result

    def _find_article_replay(
        self,
        consumed_event_id: UUID,
        *,
        session: ClientSession,
    ) -> ArticleProcessingResult | None:
        marker = self._database.processed_events.find_one(
            {"event_id": str(consumed_event_id)},
            session=session,
        )
        return self._article_processing_result(marker) if marker is not None else None

    @staticmethod
    def _processed_marker(
        consumed_event_id: UUID,
        result: ArticleProcessingResult,
        *,
        processed_at: datetime,
        fetch_artifact_id: UUID,
    ) -> MongoDocument:
        return {
            "_id": str(consumed_event_id),
            "event_id": str(consumed_event_id),
            "disposition": result.disposition.value,
            "article_id": str(result.article_id),
            "article_version_id": str(result.article_version_id),
            "outbox_event_id": (
                str(result.outbox_event_id) if result.outbox_event_id is not None else None
            ),
            "fetch_artifact_id": str(fetch_artifact_id),
            "processed_at": processed_at,
        }

    @staticmethod
    def _article_processing_result(marker: Mapping[str, object]) -> ArticleProcessingResult:
        outbox_value = marker.get("outbox_event_id")
        return ArticleProcessingResult(
            ProcessingDisposition(str(marker["disposition"])),
            UUID(str(marker["article_id"])),
            UUID(str(marker["article_version_id"])),
            UUID(str(outbox_value)) if outbox_value else None,
        )

    def _find_replay(self, consumed_event_id: str) -> ArticleWriteResult | None:
        marker = self._database.processed_events.find_one({"event_id": consumed_event_id})
        if marker is None:
            return None
        return ArticleWriteResult(
            article_id=self._required_string(marker, "article_id"),
            outbox_event_id=self._required_string(marker, "outbox_event_id"),
            created=False,
        )

    @staticmethod
    def _required_string(document: Mapping[str, object], field: str) -> str:
        value = document.get(field)
        if not isinstance(value, str) or not value:
            raise ValueError(f"{field} must be a non-empty string")
        return value

    @staticmethod
    def _required_int(document: Mapping[str, object], field: str) -> int:
        value = document.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise ValueError(f"{field} must be a positive integer")
        return value
