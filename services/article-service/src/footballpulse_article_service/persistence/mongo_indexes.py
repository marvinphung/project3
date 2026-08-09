from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.database import Database

IndexKey = tuple[str, int]


@dataclass(frozen=True, slots=True)
class IndexDefinition:
    name: str
    keys: tuple[IndexKey, ...]
    unique: bool = False

    def to_index_model(self) -> IndexModel:
        return IndexModel(list(self.keys), name=self.name, unique=self.unique)


_INDEX_DEFINITIONS: Final = {
    "source_articles": (
        IndexDefinition(
            name="uq_source_articles_canonical_version",
            keys=(("canonical_article_id", ASCENDING), ("version", ASCENDING)),
            unique=True,
        ),
        IndexDefinition(
            name="ix_source_articles_canonical_url_collected",
            keys=(("canonical_url", ASCENDING), ("collected_at", DESCENDING)),
        ),
        IndexDefinition(
            name="ix_source_articles_content_hash",
            keys=(("content_hash", ASCENDING),),
        ),
    ),
    "article_enrichments": (
        IndexDefinition(
            name="uq_article_enrichments_run",
            keys=(
                ("article_id", ASCENDING),
                ("input_hash", ASCENDING),
                ("model", ASCENDING),
                ("prompt_version", ASCENDING),
            ),
            unique=True,
        ),
        IndexDefinition(
            name="ix_article_enrichments_status_processed",
            keys=(("validation_status", ASCENDING), ("processed_at", DESCENDING)),
        ),
    ),
    "duplicate_links": (
        IndexDefinition(
            name="uq_duplicate_links_relationship",
            keys=(
                ("article_version_id", ASCENDING),
                ("primary_article_version_id", ASCENDING),
                ("duplicate_type", ASCENDING),
            ),
            unique=True,
        ),
    ),
    "processed_events": (
        IndexDefinition(
            name="uq_processed_events_event_id",
            keys=(("event_id", ASCENDING),),
            unique=True,
        ),
        IndexDefinition(
            name="ix_processed_events_processed_at",
            keys=(("processed_at", DESCENDING),),
        ),
    ),
    "outbox": (
        IndexDefinition(
            name="uq_outbox_event_id",
            keys=(("event_id", ASCENDING),),
            unique=True,
        ),
        IndexDefinition(
            name="ix_outbox_status_available",
            keys=(("status", ASCENDING), ("available_at", ASCENDING)),
        ),
    ),
}

INDEX_DEFINITIONS = MappingProxyType(_INDEX_DEFINITIONS)
COLLECTION_NAMES = tuple(_INDEX_DEFINITIONS)


def bootstrap_indexes(database: Database[dict[str, object]]) -> None:
    for collection_name, definitions in INDEX_DEFINITIONS.items():
        database[collection_name].create_indexes(
            [definition.to_index_model() for definition in definitions]
        )
