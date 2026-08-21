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
        self.news_content = FakeMongoCollection()
        self.news_entities = FakeMongoCollection()


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


def test_publisher_backfill_articles() -> None:
    mongo = FakeMongoDatabase()
    postgres_mock = MagicMock()
    conn_mock = MagicMock()
    postgres_mock.connect.return_value.__enter__.return_value = conn_mock
    postgres_mock.begin.return_value.__enter__.return_value = conn_mock

    art_id = uuid4()
    conn_mock.execute.return_value.mappings.return_value.all.return_value = [
        {
            "id": art_id,
            "title": "Arsenal Title",
            "description": "Short description",
            "url": "https://example.com/art",
            "canonical_url": "https://example.com/art",
        }
    ]

    mongo.news_content.insert_one(
        {
            "_id": art_id,
            "content": "Full article body content here.",
        }
    )

    publisher = V2Publisher(mongo=mongo, postgres=postgres_mock)  # type: ignore[arg-type]
    count = publisher.backfill_source_articles()
    assert count == 1
    assert conn_mock.execute.call_count >= 2


def test_refresh_popularity_upserts_entities_from_news_entities() -> None:
    mongo = FakeMongoDatabase()
    postgres_mock = MagicMock()
    conn_mock = MagicMock()
    postgres_mock.begin.return_value.__enter__.return_value = conn_mock

    article_id = uuid4()
    player_id = UUID("22222222-2222-2222-2222-222222222222")
    crawl_date = datetime.now(UTC)

    mongo.news_metadata.insert_one(
        {
            "_id": article_id,
            "title": "Bukayo Saka update",
            "crawl_date": crawl_date,
        }
    )
    mongo.news_entities.insert_one(
        {
            "_id": article_id,
            "entities": [
                {
                    "canonical_entity_id": player_id,
                    "canonical_name": "Bukayo Saka",
                    "label": "PLAYER",
                },
                {
                    "canonical_entity_id": player_id,
                    "canonical_name": "Bukayo Saka",
                    "label": "PLAYER",
                },
            ],
        }
    )

    publisher = V2Publisher(mongo=mongo, postgres=postgres_mock)  # type: ignore[arg-type]
    publisher.refresh_popularity_scores()

    execute_params: list[dict[str, Any]] = []
    for call in conn_mock.execute.call_args_list:
        if len(call.args) <= 1:
            continue
        params = call.args[1]
        if isinstance(params, list):
            execute_params.extend(params)
        else:
            execute_params.append(params)
    upsert_params = next(params for params in execute_params if params.get("canonical_name") == "Bukayo Saka")
    assert upsert_params["entity_type"] == "PLAYER"
    assert upsert_params["mention_count_24h"] == 1
