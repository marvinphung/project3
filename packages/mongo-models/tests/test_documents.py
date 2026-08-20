from datetime import UTC, datetime
from uuid import uuid4

from footballpulse_mongo_models import (
    CanonicalEntity,
    EntityMention,
    EntityTimelineSummary,
    NewsContent,
    NewsEntity,
    NewsMetadata,
)


def test_metadata_serializes_uuid_as_mongo_id_and_has_v2_collection_name() -> None:
    article_id = uuid4()
    document = NewsMetadata.model_construct(
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
    assert NewsMetadata.Settings.name == "news_metadata"
    assert "batch_id" not in document.model_dump()


def test_content_keeps_cleaned_and_filtered_article_text() -> None:
    now = datetime.now(UTC)
    document = NewsContent.model_construct(
        id=uuid4(),
        content="Clean text",
        filtered_content="Filtered text",
        cleaned_at=now,
        filtered_at=now,
        extractor="TRAFILATURA",
        extraction_status="SUCCESS",
    )

    assert NewsContent.Settings.name == "news_content"
    assert document.content == "Clean text"
    assert document.filtered_content == "Filtered text"
    assert "raw_html" not in document.model_dump()


def test_entity_timeline_summary_model() -> None:
    summary_id = uuid4()
    entity_id = uuid4()
    now = datetime.now(UTC)
    summary = EntityTimelineSummary.model_construct(
        id=summary_id,
        entity_id=entity_id,
        canonical_name="Arsenal",
        entity_type="CLUB",
        window_start=now,
        window_end=now,
        article_ids=[uuid4()],
        article_count=1,
        entities_50=["Arsenal"],
        entities_80=["Arsenal"],
        aggregated_news="Arsenal won.",
        short_description="Arsenal Victory",
        status="COMPLETED",
        created_at=now,
        updated_at=now,
    )

    assert EntityTimelineSummary.Settings.name == "entity_timeline_summaries"
    assert summary.id == summary_id
    assert summary.canonical_name == "Arsenal"
    assert summary.article_count == 1

