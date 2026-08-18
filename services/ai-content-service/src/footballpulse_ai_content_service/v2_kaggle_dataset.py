from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pymongo.database import Database

MongoDocument = dict[str, Any]


class V2KaggleDatasetBuilder:
    """Builds one complete local dataset from the current Mongo backlog."""

    def __init__(self, database: Database[MongoDocument]) -> None:
        self._database = database

    def build(self, target: Path) -> int:
        if target.exists():
            raise FileExistsError(target)
        target.mkdir(parents=True, mode=0o700)
        output = target / "articles.jsonl"
        count = 0
        with output.open("w", encoding="utf-8") as stream:
            for document in self._backlog():
                stream.write(json.dumps(document, ensure_ascii=False, default=str) + "\n")
                count += 1
        os.chmod(output, 0o600)
        return count

    def _backlog(self):
        pipeline = [
            {"$lookup": {"from": "news_enrichments", "localField": "_id", "foreignField": "_id", "as": "enrichment"}},
            {"$match": {"enrichment": {"$size": 0}}},
            {"$lookup": {"from": "news_metadata", "localField": "_id", "foreignField": "_id", "as": "metadata"}},
            {"$unwind": "$metadata"},
            {"$project": {"article_id": "$_id", "content": 1, "metadata": 1}},
        ]
        yield from self._database.news_content.aggregate(pipeline)
