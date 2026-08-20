from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from footballpulse_entities_extraction_service.canonical import (
    CanonicalRegistry,
    deterministic_entity_id,
    normalize_text,
)
from footballpulse_entities_extraction_service.v2_processor import V2EntityProcessor


class FakeCollection:
    def __init__(self) -> None:
        self.docs: dict[Any, dict[str, Any]] = {}

    def insert_one(self, doc: dict[str, Any]) -> None:
        self.docs[doc["_id"]] = doc

    def find(self, query: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if query and query.get("status") == "ACTIVE":
            return [d for d in self.docs.values() if d.get("status") == "ACTIVE"]
        return list(self.docs.values())

    def find_one(self, query: dict[str, Any]) -> dict[str, Any] | None:
        return self.docs.get(query.get("_id"))

    def update_one(self, filter_query: dict[str, Any], update_doc: dict[str, Any]) -> None:
        doc_id = filter_query.get("_id")
        if doc_id in self.docs:
            if "$set" in update_doc:
                self.docs[doc_id].update(update_doc["$set"])

    def replace_one(
        self,
        filter_query: dict[str, Any],
        replacement: dict[str, Any],
        upsert: bool = False,
    ) -> None:
        doc_id = filter_query.get("_id")
        if doc_id in self.docs or upsert:
            self.docs[doc_id] = replacement


class FakeDatabase:
    def __init__(self) -> None:
        self.canonical_entities = FakeCollection()
        self.news_content = FakeCollection()
        self.news_entities = FakeCollection()


def test_alias_replacement_and_longest_match() -> None:
    entities = [
        {
            "_id": UUID("11111111-1111-1111-1111-111111111111"),
            "entity_type": "CLUB",
            "canonical_name": "Manchester United",
            "aliases": [
                {"value": "Man Utd", "normalized_value": "man utd", "case_sensitive": False},
                {"value": "MU", "normalized_value": "mu", "case_sensitive": False},
                {"value": "Manchester United FC", "normalized_value": "manchester united fc", "case_sensitive": False},
            ],
        },
        {
            "_id": UUID("22222222-2222-2222-2222-222222222222"),
            "entity_type": "CLUB",
            "canonical_name": "Manchester City",
            "aliases": [
                {"value": "Man City", "normalized_value": "man city", "case_sensitive": False},
                {"value": "City", "normalized_value": "city", "case_sensitive": False},
            ],
        },
    ]

    registry = CanonicalRegistry(entities)

    text = "MU defeated Man City in the derby while Manchester United FC celebrated."
    filtered = registry.replace_aliases(text)

    assert "Manchester United defeated Manchester City in the derby while Manchester United celebrated." == filtered


def test_entity_resolution() -> None:
    club_id = UUID("11111111-1111-1111-1111-111111111111")
    entities = [
        {
            "_id": club_id,
            "entity_type": "CLUB",
            "canonical_name": "Arsenal",
            "aliases": [
                {"value": "Gunners", "normalized_value": "gunners"},
            ],
        },
    ]
    registry = CanonicalRegistry(entities)

    # Matched club
    eid, name = registry.resolve_entity("Gunners", "CLUB")
    assert eid == club_id
    assert name == "Arsenal"

    # Unseeded player fallback
    player_id, player_name = registry.resolve_entity("Bukayo Saka", "PLAYER")
    assert player_name == "Bukayo Saka"
    assert player_id == deterministic_entity_id("PLAYER", "Bukayo Saka")


def test_v2_processor_pipeline() -> None:
    db = FakeDatabase()
    article_id = uuid4()
    club_id = UUID("11111111-1111-1111-1111-111111111111")

    db.canonical_entities.insert_one(
        {
            "_id": club_id,
            "entity_type": "CLUB",
            "canonical_name": "Real Madrid",
            "aliases": [
                {"value": "Real", "normalized_value": "real"},
                {"value": "Los Blancos", "normalized_value": "los blancos"},
            ],
            "status": "ACTIVE",
        }
    )

    db.news_content.insert_one(
        {
            "_id": article_id,
            "content": "Los Blancos won the match. Vinicius Junior scored a brace.",
            "cleaned_at": datetime.now(UTC),
        }
    )

    def mock_extractor(text: str) -> list[dict[str, Any]]:
        entities = []
        if "Real Madrid" in text:
            idx = text.find("Real Madrid")
            entities.append({"text": "Real Madrid", "label": "club", "score": 0.95, "start": idx, "end": idx + 11})
        if "Vinicius Junior" in text:
            idx = text.find("Vinicius Junior")
            entities.append({"text": "Vinicius Junior", "label": "player", "score": 0.99, "start": idx, "end": idx + 15})
        entities.append({"text": "won", "label": "competition", "score": 0.94, "start": 12, "end": 15})
        return entities

    processor = V2EntityProcessor(database=db, extractor=mock_extractor)  # type: ignore[arg-type]
    processed_id = processor.process_article(article_id)

    assert processed_id == article_id

    # Verify news_content was updated with filtered_content
    updated_content = db.news_content.find_one({"_id": article_id})
    assert updated_content is not None
    assert updated_content["filtered_content"] == "Real Madrid won the match. Vinicius Junior scored a brace."
    assert updated_content.get("filtered_at") is not None

    # Verify news_entities has canonicalized entities
    entity_doc = db.news_entities.find_one({"_id": article_id})
    assert entity_doc is not None
    entities = entity_doc["entities"]
    assert len(entities) == 2
    assert all(entity["score"] >= 0.95 for entity in entities)
    assert entities[0]["canonical_entity_id"] == club_id
    assert entities[0]["canonical_name"] == "Real Madrid"
    assert entities[1]["canonical_name"] == "Vinicius Junior"
