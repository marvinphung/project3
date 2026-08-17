#!/usr/bin/env python3
"""Project one reviewed, real Source Article into the public PostgreSQL read model.

This is an operational bridge for records whose Kaggle summary is usable but whose
structured claims require an editor to supply exact source evidence. It never accepts
free-form evidence: the quote must occur exactly once in the crawled MongoDB content.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, NAMESPACE_URL, uuid5

from footballpulse_runtime_config import configure_logging, log_event
from pymongo import MongoClient
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from footballpulse_content_service.editorial.postgres_publication_repository import (
    PostgresPublicationRepository,
)
from footballpulse_content_service.editorial.postgres_repository import (
    PostgresEditorialRevisionRepository,
)
from footballpulse_content_service.editorial.publication import PublicationService
from footballpulse_content_service.editorial.revision import EditorialRevision, RevisionState
from footballpulse_content_service.editorial.workflow import EditorialWorkflow
from footballpulse_intelligence_service.domain.claim_confirmation import ClaimConfirmation
from footballpulse_intelligence_service.domain.delivery import OutboxEvent, ProcessedEvent
from footballpulse_intelligence_service.domain.entity import EntityType
from footballpulse_intelligence_service.domain.story import (
    Claim,
    ClaimEvidence,
    ClaimPredicate,
    Story,
    StoryEntity,
    StoryEventType,
    StorySource,
)
from footballpulse_intelligence_service.domain.timeline import TimelineEntry, timeline_window_start
from footballpulse_intelligence_service.persistence.story_repository import PostgresStoryRepository
from footballpulse_intelligence_service.persistence.timeline_repository import (
    PostgresTimelineRepository,
)

LOGGER = logging.getLogger("footballpulse.reviewed_publication")
ARTICLE_ID = UUID("c505e3f7-7c87-5432-ae63-40ef0f2d76c5")
ARSENAL_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c8103")
EVIDENCE = (
    "Arsenal have shipped an average of 2.3 goals in their three friendlies "
    "played since the start of August"
)
TITLE_EN = "Arsenal's pre-season defence faces an early test"
BODY_EN = (
    "Arsenal have looked defensively weak in pre-season as the new campaign approaches. "
    "Sky Sports reports that the club conceded an average of 2.3 goals across its three "
    "August friendlies, while William Saliba remains unavailable with a back injury."
)
TITLE_VI = "Hàng thủ Arsenal đối mặt bài kiểm tra sớm trước mùa giải mới"
BODY_VI = (
    "Arsenal đang bộc lộ vấn đề ở hàng phòng ngự khi mùa giải mới đến gần. Theo Sky Sports, "
    "đội bóng để thủng lưới trung bình 2,3 bàn trong ba trận giao hữu từ đầu tháng 8, trong "
    "bối cảnh William Saliba vẫn vắng mặt vì chấn thương lưng."
)
SLUG = "hang-thu-arsenal-doi-mat-bai-kiem-tra-som"


def stable_id(label: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"footballpulse:{ARTICLE_ID}:{label}")


def database_url() -> URL:
    return URL.create(
        "postgresql+psycopg",
        username=os.getenv("FOOTBALLPULSE_POSTGRES_USER", "footballpulse"),
        password=os.getenv("FOOTBALLPULSE_POSTGRES_PASSWORD", "footballpulse_local_only"),
        host=os.getenv("FOOTBALLPULSE_POSTGRES_HOST", "127.0.0.1"),
        port=int(os.getenv("FOOTBALLPULSE_POSTGRES_PORT", "5432")),
        database=os.getenv("FOOTBALLPULSE_POSTGRES_DB", "footballpulse"),
    )


def main() -> None:
    configure_logging(service="reviewed-publication", level="INFO", force=True)
    mongo = MongoClient(
        os.getenv(
            "FOOTBALLPULSE_MONGODB_URL",
            "mongodb://127.0.0.1:27017/?replicaSet=rs0&directConnection=true",
        )
    )
    database = mongo[os.getenv("FOOTBALLPULSE_MONGODB_DB", "footballpulse")]
    article = database.source_articles.find_one({"article_version_id": str(ARTICLE_ID)})
    enrichment = database.article_enrichments.find_one({"article_version_id": str(ARTICLE_ID)})
    intelligence = database.article_intelligence.find_one({"article_version_id": str(ARTICLE_ID)})
    if article is None or enrichment is None or intelligence is None:
        raise RuntimeError("article must complete crawl, intelligence and enrichment first")
    content = str(article["cleaned_content"])
    if content.count(EVIDENCE) != 1:
        raise RuntimeError("reviewed evidence must be one exact, unique source substring")
    entity_ids = {UUID(value["entity_id"]) for value in intelligence["canonical_entities"]}
    if ARSENAL_ID not in entity_ids:
        raise RuntimeError("reviewed subject must exist in canonical intelligence output")
    ai_summary = str(enrichment.get("summary_en", "")).strip()
    if not ai_summary or ai_summary not in content:
        raise RuntimeError("AI summary/title must be directly grounded in crawled content")

    observed_at = article.get("collected_at") or datetime.now(UTC)
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=UTC)
    now = datetime.now(UTC)
    source_id = UUID(article["source_id"])
    story_id = stable_id("story")
    story_source_id = stable_id("story-source")
    claim_id = stable_id("claim")
    story = Story.create(
        story_id=story_id,
        event_type=StoryEventType.MATCH,
        first_seen_at=observed_at,
        confidence_score=Decimal("0.8000"),
    )
    source = StorySource.create(
        link_id=story_source_id,
        story_id=story_id,
        article_version_id=ARTICLE_ID,
        source_id=source_id,
        source_reliability_tier=2,
        published_at=observed_at,
        observed_at=observed_at,
    )
    entity = StoryEntity.create(
        link_id=stable_id("story-entity-arsenal"),
        story_id=story_id,
        entity_id=ARSENAL_ID,
        entity_type=EntityType.CLUB,
        now=observed_at,
    )
    claim = Claim.create(
        claim_id=claim_id,
        story_id=story_id,
        subject_entity_id=ARSENAL_ID,
        predicate=ClaimPredicate.MATCH_RESULT,
        object_entity_id=None,
        object_value={"metric": "goals_conceded_average", "value": 2.3, "matches": 3},
        statement_en=EVIDENCE,
        certainty=Decimal("0.8000"),
        occurred_at=None,
        occurred_at_bucket=None,
        now=observed_at,
        confirmation=ClaimConfirmation.REPORTED,
    )
    start = content.index(EVIDENCE)
    evidence = ClaimEvidence.create(
        evidence_id=stable_id("claim-evidence"),
        claim_id=claim_id,
        story_source_id=story_source_id,
        quote=EVIDENCE,
        start=start,
        end=start + len(EVIDENCE),
        now=observed_at,
    )
    processed = ProcessedEvent.create(
        record_id=stable_id("processed-event"),
        consumer_name="reviewed-story-projector-v1",
        event_id=stable_id("reviewed-event"),
        event_type="article.reviewed.v1",
        processed_at=now,
    )
    outbox = OutboxEvent.create(
        event_id=stable_id("story-created-outbox"),
        aggregate_type="STORY",
        aggregate_id=story_id,
        event_type="story.created.v1",
        deduplication_key=f"story.created:{story_id}:1",
        payload={"story_id": str(story_id), "version": 1, "reviewed": True},
        now=now,
    )

    engine = create_engine(database_url(), pool_pre_ping=True)
    created = PostgresStoryRepository(engine).create_from_event(
        story=story,
        sources=(source,),
        entities=(entity,),
        claims=(claim,),
        evidence=(evidence,),
        processed_event=processed,
        outbox_events=(outbox,),
    )
    timeline = TimelineEntry.create(
        entry_id=stable_id("timeline"),
        story_id=story_id,
        window_start=timeline_window_start(observed_at),
        summary_en=BODY_EN,
        summary_vi=BODY_VI,
        confirmation=ClaimConfirmation.REPORTED,
        used_claim_ids=(claim_id,),
        source_article_ids=(ARTICLE_ID,),
        created_at=now,
    )
    timeline_created = PostgresTimelineRepository(engine).add_once(timeline)

    generated_article_id = stable_id("generated-article")
    revisions = PostgresEditorialRevisionRepository(engine)
    revision = revisions.get_current(generated_article_id)
    if revision is None:
        revision = EditorialRevision.create(
            revision_id=stable_id("revision-1"),
            generated_article_id=generated_article_id,
            story_id=story_id,
            story_version=1,
            revision_number=1,
            title_en=TITLE_EN,
            body_en=BODY_EN,
            title_vi=TITLE_VI,
            body_vi=BODY_VI,
            created_at=now,
        )
        revisions.add(revision)
    workflow = EditorialWorkflow(revisions)
    if revision.state is RevisionState.DRAFT:
        revision = workflow.submit_for_review(
            generated_article_id, expected_revision_number=1, now=now
        )
    if revision.state is RevisionState.NEEDS_REVIEW:
        revision = workflow.approve(generated_article_id, expected_revision_number=1, now=now)
    publication = PublicationService(PostgresPublicationRepository(engine)).publish(
        revision=revision,
        slug=SLUG,
        idempotency_key=f"reviewed-publication:{ARTICLE_ID}",
        published_at=now,
    )
    log_event(
        LOGGER,
        "reviewed_article_published",
        article_version_id=str(ARTICLE_ID),
        story_id=str(story_id),
        publication_id=str(publication.id),
        story_created=created,
        timeline_created=timeline_created,
        source_url=article["canonical_url"],
        ai_model=enrichment.get("model_version"),
    )
    engine.dispose()
    mongo.close()


if __name__ == "__main__":
    main()
