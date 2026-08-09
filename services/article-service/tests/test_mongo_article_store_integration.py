from __future__ import annotations

import os
from collections.abc import Iterator
from uuid import uuid4

import pytest
from footballpulse_article_service.persistence.mongo_article_store import MongoArticleStore
from footballpulse_article_service.persistence.mongo_indexes import bootstrap_indexes
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError


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
