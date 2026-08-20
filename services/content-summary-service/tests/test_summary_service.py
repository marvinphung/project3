from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from footballpulse_content_summary_service.llm_client import MockLLMClient
from footballpulse_content_summary_service.summary_generator import SummaryGenerator
from footballpulse_content_summary_service.thresholds import compute_entity_thresholds
from footballpulse_content_summary_service.window_planner import (
    floor_3h_window,
    get_latest_closed_3h_window,
    get_utc_3h_windows,
)


class FakeCollection:
    def __init__(self) -> None:
        self.docs: dict[Any, dict[str, Any]] = {}

    def insert_one(self, doc: dict[str, Any]) -> None:
        self.docs[doc["_id"]] = doc

    def find(self, query: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        results = list(self.docs.values())
        if query and "$or" in query:
            # Simple query handling for published_time in window
            filtered = []
            for d in results:
                pub = d.get("published_time") or d.get("crawl_date")
                if pub:
                    cond = query["$or"][0].get("published_time", {})
                    gte = cond.get("$gte")
                    lt = cond.get("$lt")
                    if gte and lt and gte <= pub < lt:
                        filtered.append(d)
            return filtered
        if query and "_id" in query and "$in" in query["_id"]:
            allowed = set(query["_id"]["$in"])
            return [d for d in results if d["_id"] in allowed]
        return results

    def find_one(self, query: dict[str, Any]) -> dict[str, Any] | None:
        doc_id = query.get("_id")
        doc = self.docs.get(doc_id)
        if doc and query.get("status") and doc.get("status") != query.get("status"):
            return None
        return doc

    def replace_one(self, query: dict[str, Any], doc: dict[str, Any], upsert: bool = False) -> None:
        self.docs[query["_id"]] = doc


class FakeDatabase:
    def __init__(self) -> None:
        self.news_metadata = FakeCollection()
        self.news_content = FakeCollection()
        self.news_entities = FakeCollection()
        self.entity_timeline_summaries = FakeCollection()


def test_window_planner() -> None:
    dt = datetime(2026, 8, 20, 7, 45, tzinfo=UTC)
    floored = floor_3h_window(dt)
    assert floored == datetime(2026, 8, 20, 6, 0, tzinfo=UTC)

    start, end = get_latest_closed_3h_window(dt)
    assert start == datetime(2026, 8, 20, 3, 0, tzinfo=UTC)
    assert end == datetime(2026, 8, 20, 6, 0, tzinfo=UTC)

    windows = get_utc_3h_windows(
        datetime(2026, 8, 20, 0, 0, tzinfo=UTC),
        datetime(2026, 8, 20, 9, 0, tzinfo=UTC),
    )
    assert len(windows) == 3
    assert windows[0] == (datetime(2026, 8, 20, 0, 0, tzinfo=UTC), datetime(2026, 8, 20, 3, 0, tzinfo=UTC))


def test_compute_entity_thresholds() -> None:
    # 1 article: all entities should be >=50% and >=80%
    single_article = [["Arsenal", "Bukayo Saka", "Mikel Arteta"]]
    e50, e80 = compute_entity_thresholds(single_article)
    assert "Arsenal" in e50 and "Arsenal" in e80
    assert "Bukayo Saka" in e50 and "Bukayo Saka" in e80

    # 3 articles:
    # Arsenal in 3/3 (100%) -> in e50 and e80
    # Saka in 2/3 (66.7%) -> in e50, not e80 (0.8 * 3 = 2.4, so 3 needed for 80%)
    # Chelsea in 1/3 (33.3%) -> in neither
    multi_articles = [
        ["Arsenal", "Saka", "Chelsea"],
        ["Arsenal", "Saka"],
        ["Arsenal", "Saliba"],
    ]
    e50, e80 = compute_entity_thresholds(multi_articles)
    assert e50 == ["Arsenal", "Saka"]
    assert e80 == ["Arsenal"]


def test_summary_generator_flow() -> None:
    db = FakeDatabase()
    window_start = datetime(2026, 8, 20, 3, 0, tzinfo=UTC)
    window_end = datetime(2026, 8, 20, 6, 0, tzinfo=UTC)

    art1_id = uuid4()
    art2_id = uuid4()
    arsenal_id = UUID("11111111-1111-1111-1111-111111111111")
    saka_id = UUID("22222222-2222-2222-2222-222222222222")

    # Insert metadata
    db.news_metadata.insert_one(
        {
            "_id": art1_id,
            "title": "Arsenal win thriller",
            "published_time": datetime(2026, 8, 20, 4, 0, tzinfo=UTC),
        }
    )
    db.news_metadata.insert_one(
        {
            "_id": art2_id,
            "title": "Arsenal press conference",
            "published_time": datetime(2026, 8, 20, 5, 0, tzinfo=UTC),
        }
    )

    # Insert content
    db.news_content.insert_one({"_id": art1_id, "content": "Arsenal won 3-2 against opponent with Saka shining."})
    db.news_content.insert_one({"_id": art2_id, "content": "Arsenal manager praises team performance."})

    # Insert entities
    db.news_entities.insert_one(
        {
            "_id": art1_id,
            "entities": [
                {"canonical_entity_id": arsenal_id, "canonical_name": "Arsenal", "label": "CLUB"},
                {"canonical_entity_id": saka_id, "canonical_name": "Bukayo Saka", "label": "PLAYER"},
            ],
        }
    )
    db.news_entities.insert_one(
        {
            "_id": art2_id,
            "entities": [
                {"canonical_entity_id": arsenal_id, "canonical_name": "Arsenal", "label": "CLUB"},
            ],
        }
    )

    generator = SummaryGenerator(database=db, llm_client=MockLLMClient())  # type: ignore[arg-type]
    summaries = generator.process_window(window_start, window_end)

    # Arsenal has 2 articles, Saka has 1 article -> 2 summaries generated
    assert len(summaries) == 2
    arsenal_summary = next(s for s in summaries if s["canonical_name"] == "Arsenal")
    assert arsenal_summary["article_count"] == 2
    assert arsenal_summary["status"] == "COMPLETED"
    assert arsenal_summary["aggregated_news"] != ""
    assert arsenal_summary["short_description"] != ""

    # Check idempotency / skip-if-existing
    second_run = generator.process_window(window_start, window_end)
    assert len(second_run) == 2
