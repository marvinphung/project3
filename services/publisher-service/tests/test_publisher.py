from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4
from unittest.mock import MagicMock

from footballpulse_publisher_service.publisher import (
    V2Publisher,
    normalize_entity_type,
    slugify,
)


class FakeMongoCollection:
    def __init__(self) -> None:
        self.docs: dict[Any, dict[str, Any]] = {}

    def insert_one(self, doc: dict[str, Any]) -> None:
        self.docs[doc["_id"]] = doc

    def find_one(self, query: dict[str, Any]) -> dict[str, Any] | None:
        return self.docs.get(query.get("_id"))

    def find(self, query: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        results = list(self.docs.values())
        if query and "_id" in query and "$in" in query["_id"]:
            allowed = set(query["_id"]["$in"])
            return [d for d in results if d["_id"] in allowed]
        return results

    def update_one(self, query: dict[str, Any], update: dict[str, Any]) -> None:
        doc = self.docs.get(query.get("_id"))
        if doc and "$set" in update:
            doc.update(update["$set"])


class FakeMongoDatabase:
    def __init__(self) -> None:
        self.entity_timeline_summaries = FakeMongoCollection()
        self.canonical_entities = FakeMongoCollection()
        self.news_metadata = FakeMongoCollection()


def test_slugify_and_normalize_entity_type() -> None:
    assert slugify("Real Madrid C.F.") == "real-madrid-c-f"
    assert slugify("Arsenal") == "arsenal"
    assert normalize_entity_type("club") == "CLUB"
    assert normalize_entity_type("PLAYER") == "PLAYER"
    assert normalize_entity_type("manager") == "COACH"
    assert normalize_entity_type("tournament") == "COMPETITION"


def test_publisher_publishes_summary() -> None:
    mongo = FakeMongoDatabase()
    postgres_mock = MagicMock()
    conn_mock = MagicMock()
    postgres_mock.begin.return_value.__enter__.return_value = conn_mock

    summary_id = uuid4()
    entity_id = UUID("11111111-1111-1111-1111-111111111111")
    art_id = uuid4()

    mongo.entity_timeline_summaries.insert_one(
        {
            "_id": summary_id,
            "entity_id": entity_id,
            "canonical_name": "Arsenal",
            "entity_type": "CLUB",
            "window_start": datetime(2026, 8, 20, 0, 0, tzinfo=UTC),
            "window_end": datetime(2026, 8, 20, 3, 0, tzinfo=UTC),
            "article_ids": [art_id],
            "article_count": 1,
            "entities_50": ["Arsenal"],
            "entities_80": ["Arsenal"],
            "aggregated_news": "Arsenal match report.",
            "short_description": "Arsenal Win",
            "status": "COMPLETED",
            "published_at": None,
        }
    )

    mongo.news_metadata.insert_one(
        {
            "_id": art_id,
            "title": "Arsenal vs Chelsea",
            "url": "https://example.com/art1",
            "canonical_url": "https://example.com/art1",
            "source_name": "Example",
            "domain_name": "example.com",
            "description": "Desc",
            "image_url": "https://example.com/img.jpg",
            "published_time": datetime(2026, 8, 20, 1, 0, tzinfo=UTC),
            "crawl_date": datetime(2026, 8, 20, 2, 0, tzinfo=UTC),
            "content_hash": "hash1",
        }
    )

    publisher = V2Publisher(mongo=mongo, postgres=postgres_mock)  # type: ignore[arg-type]
    published = publisher.publish_summary(summary_id)

    assert published is True
    assert conn_mock.execute.call_count >= 4
    updated_summary = mongo.entity_timeline_summaries.find_one({"_id": summary_id})
    assert updated_summary is not None
    assert updated_summary["published_at"] is not None
