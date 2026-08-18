from datetime import UTC, datetime
from uuid import uuid4

from footballpulse_mongo_models import NewsContent, NewsMetadata


def test_metadata_serializes_uuid_as_mongo_id_and_has_v2_collection_name() -> None:
    article_id = uuid4()
    document = NewsMetadata(
        id=article_id,
        url="https://example.com/news",
        canonical_url="https://example.com/news",
        domain_name="example.com",
        source_name="Example",
        title="A title",
        crawl_date=datetime.now(UTC),
        content_hash="abc",
    )

    assert document.id == article_id
    assert document.get_settings().name == "news_metadata"
    assert "batch_id" not in document.model_dump()


def test_content_keeps_only_cleaned_article_text() -> None:
    document = NewsContent(
        id=uuid4(),
        content="Clean text",
        cleaned_at=datetime.now(UTC),
        extractor="TRAFILATURA",
        extraction_status="SUCCESS",
    )

    assert document.get_settings().name == "news_content"
    assert "raw_html" not in document.model_dump()
