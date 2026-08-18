from __future__ import annotations

import sys
from pathlib import Path

from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.extend(
    [
        str(ROOT / "packages/shared/src"),
        str(ROOT / "services/crawler-service/src"),
    ]
)

from footballpulse_crawler_service.discovery.rss import parse_rss
from footballpulse_crawler_service.discovery.v2_policy import select_new_candidates
from footballpulse_crawler_service.extraction.processor import ArticleContentProcessor
from footballpulse_crawler_service.extraction.service import ExtractedArticle
from footballpulse_crawler_service.persistence.mongo_v2 import V2MongoArticleWriter


RSS = ROOT / "tests/fixtures/mock-news/rss/trusted-general.xml"
ARTICLES = ROOT / "tests/fixtures/mock-news/articles"
URL_TO_FIXTURE = {
    "https://trusted-a.test/football/official-denial": "official-denial.html",
    "https://trusted-a.test/football/vinicius-injury": "injury.html",
    "https://trusted-b.test/football/real-madrid-arsenal": "match.html",
}


def main() -> None:
    feed = parse_rss(RSS.read_bytes(), allowed_domains=("trusted-a.test", "trusted-b.test"), max_entries=500)
    existing: set[object] = set()
    candidates = select_new_candidates(
        [entry.url for entry in feed.entries],
        exists=lambda article_id: article_id in existing,
        candidate_limit=500,
        fetch_limit=100,
    )
    if len(candidates) != len(feed.entries):
        raise AssertionError("first crawl unexpectedly dropped fixture candidates")

    client = MongoClient(
        "mongodb://127.0.0.1:27117/?directConnection=true",
        uuidRepresentation="standard",
    )
    database = client["footballpulse_v2"]
    writer = V2MongoArticleWriter(database)
    processor = ArticleContentProcessor()
    written = []
    for candidate in candidates[:3]:
        fixture = URL_TO_FIXTURE[candidate.url]
        html = (ARTICLES / fixture).read_bytes()
        extraction = processor.process(html, url=candidate.url)
        result = writer.write(
            ExtractedArticle(
                source_key="fixture-source",
                requested_url=candidate.url,
                final_url=candidate.url,
                content_type="text/html",
                etag=None,
                last_modified=None,
                raw_html=html,
                extraction=extraction,
            ),
            source_name="Fixture Source",
        )
        if result != candidate.article_id:
            raise AssertionError("writer returned an unexpected deterministic article id")
        written.append(result)

    stored = database.news_metadata.count_documents({"_id": {"$in": written}})
    content = database.news_content.count_documents({"_id": {"$in": written}})
    if stored != 3 or content != 3:
        raise AssertionError(f"expected 3 metadata/content documents, got {stored}/{content}")

    second_pass = select_new_candidates(
        [entry.url for entry in feed.entries],
        exists=lambda article_id: database.news_metadata.find_one({"_id": article_id}) is not None,
        candidate_limit=500,
        fetch_limit=100,
    )
    if len(second_pass) != 3:
        raise AssertionError(f"expected 3 not-yet-crawled fixture candidates, got {len(second_pass)}")
    print(f"v2 crawler smoke passed: candidates={len(candidates)} stored={stored} remaining={len(second_pass)}")


if __name__ == "__main__":
    main()
