from footballpulse_article_service.persistence.mongo_indexes import INDEX_DEFINITIONS


def test_article_service_owns_the_expected_mongo_collections() -> None:
    assert set(INDEX_DEFINITIONS) == {
        "source_articles",
        "article_enrichments",
        "duplicate_links",
        "processed_events",
        "outbox",
    }


def test_idempotency_indexes_are_unique_and_stably_named() -> None:
    indexes_by_name = {
        index.name: index
        for collection_indexes in INDEX_DEFINITIONS.values()
        for index in collection_indexes
    }

    assert indexes_by_name["uq_source_articles_canonical_version"].keys == (
        ("canonical_article_id", 1),
        ("version", 1),
    )
    assert indexes_by_name["uq_source_articles_canonical_version"].unique is True
    assert indexes_by_name["uq_article_enrichments_run"].unique is True
    assert indexes_by_name["uq_duplicate_links_relationship"].unique is True
    assert indexes_by_name["uq_processed_events_event_id"].unique is True
    assert indexes_by_name["uq_outbox_event_id"].unique is True
