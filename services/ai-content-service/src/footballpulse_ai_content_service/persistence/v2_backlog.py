from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import UUID

from pymongo.database import Database

MongoDocument = dict[str, Any]


class V2EnrichmentBacklog:
    """Read-only backlog view; processing state is intentionally not stored in Mongo."""

    def __init__(self, database: Database[MongoDocument]) -> None:
        self._database = database

    def iter_unenriched(self) -> Iterator[MongoDocument]:
        pipeline = [
            {"$match": {"_id": {"$exists": True}}},
            {
                "$lookup": {
                    "from": "news_enrichments",
                    "localField": "_id",
                    "foreignField": "_id",
                    "as": "enrichment",
                }
            },
            {"$match": {"enrichment": {"$size": 0}}},
            {
                "$lookup": {
                    "from": "news_metadata",
                    "localField": "_id",
                    "foreignField": "_id",
                    "as": "metadata",
                }
            },
            {"$unwind": "$metadata"},
            {
                "$project": {
                    "_id": 1,
                    "content": 1,
                    "metadata": 1,
                }
            },
        ]
        yield from self._database.news_content.aggregate(pipeline)

    @staticmethod
    def article_id(document: MongoDocument) -> UUID:
        value = document.get("_id")
        if isinstance(value, UUID):
            return value
        if isinstance(value, str):
            return UUID(value)
        raise ValueError("v2 backlog document has an invalid article id")
