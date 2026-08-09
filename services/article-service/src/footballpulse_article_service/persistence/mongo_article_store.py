from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from pymongo import ReadPreference
from pymongo.client_session import ClientSession
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

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
