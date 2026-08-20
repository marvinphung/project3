from __future__ import annotations

import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.extend([
    str(ROOT / "packages/runtime-config/src"),
    str(ROOT / "packages/shared/src"),
    str(ROOT / "packages/event-contracts/src"),
    str(ROOT / "services/entities-extraction-service/src"),
    str(ROOT / "packages/pipeline/src"),
])

from footballpulse_entities_extraction_service.v2_processor import V2EntityProcessor
from footballpulse_pipeline.cli import _extract_entities

def main() -> None:
    mongo_url = os.getenv("FOOTBALLPULSE_MONGODB_URL", "mongodb://127.0.0.1:27117/?directConnection=true")
    db_name = os.getenv("FOOTBALLPULSE_MONGODB_DB", "footballpulse_v2")

    print(f"Connecting to MongoDB at {mongo_url} (db={db_name})...")
    client = MongoClient(mongo_url, uuidRepresentation="standard")
    db = client[db_name]

    articles = list(db.news_content.find({}, {"_id": 1, "content": 1}))
    total = len(articles)
    print(f"Found {total} articles in news_content to process with GLiNER2 Large...")

    processor = V2EntityProcessor(database=db, extractor=_extract_entities, workers=1)

    start_total = time.monotonic()
    success_count = 0
    total_entities = 0

    for idx, doc in enumerate(articles, 1):
        article_id = doc["_id"]
        start_art = time.monotonic()
        try:
            processor.process_article(article_id)
            duration = (time.monotonic() - start_art) * 1000.0
            entity_doc = db.news_entities.find_one({"_id": article_id})
            cnt = len(entity_doc.get("entities", [])) if entity_doc else 0
            total_entities += cnt
            success_count += 1
            if idx % 10 == 0 or idx == total or idx == 1:
                print(f"[{idx}/{total}] Processed article {article_id} in {duration:.1f}ms (entities: {cnt})")
        except Exception as err:
            print(f"[{idx}/{total}] ERROR processing article {article_id}: {err}")

    total_time = time.monotonic() - start_total
    avg_per_doc = (total_time / total) * 1000.0 if total else 0.0

    print("\n" + "=" * 60)
    print("REPROCESS COMPLETED")
    print("=" * 60)
    print(f"Total articles processed: {success_count}/{total}")
    print(f"Total entities extracted: {total_entities}")
    print(f"Average entities/article: {total_entities / total:.2f}" if total else "0")
    print(f"Total execution time: {total_time:.2f}s")
    print(f"Average latency: {avg_per_doc:.2f}ms/article")
    print(f"Throughput: {total / total_time:.2f} articles/sec")
    print(f"Total documents now in news_entities: {db.news_entities.count_documents({})}")
    print("=" * 60)

if __name__ == "__main__":
    main()
