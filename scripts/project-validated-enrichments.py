#!/usr/bin/env python3
"""Project validated Mongo enrichments into Story/timeline/editorial drafts.

The command is deliberately draft-only: it never auto-publishes Vietnamese copy.
It is idempotent per article version and leaves content_schema.publications untouched.
"""

from __future__ import annotations

import argparse
import logging
import os
from datetime import UTC, datetime
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

from pymongo import MongoClient
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from footballpulse_content_service.editorial.postgres_repository import (
    PostgresEditorialRevisionRepository,
)
from footballpulse_content_service.editorial.revision import EditorialRevision
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
from footballpulse_intelligence_service.persistence.timeline_repository import PostgresTimelineRepository

LOGGER = logging.getLogger("footballpulse.validated_projector")


def stable(article_id: UUID, label: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"footballpulse:validated-projector:{article_id}:{label}")


def database_url() -> URL:
    return URL.create(
        "postgresql+psycopg",
        username=os.getenv("FOOTBALLPULSE_POSTGRES_USER", "footballpulse"),
        password=os.getenv("FOOTBALLPULSE_POSTGRES_PASSWORD", "footballpulse_local_only"),
        host=os.getenv("FOOTBALLPULSE_POSTGRES_HOST", "127.0.0.1"),
        port=int(os.getenv("FOOTBALLPULSE_POSTGRES_PORT", "5432")),
        database=os.getenv("FOOTBALLPULSE_POSTGRES_DB", "footballpulse"),
    )


def parse_uuid(value: object) -> UUID | None:
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def event_type(value: object) -> StoryEventType:
    try:
        return StoryEventType(str(value).upper())
    except ValueError:
        return StoryEventType.OTHER


def predicate(value: object) -> ClaimPredicate:
    try:
        return ClaimPredicate(str(value).upper())
    except ValueError:
        return ClaimPredicate.EXPRESSED_INTEREST


def confirmation(value: object) -> ClaimConfirmation:
    try:
        return ClaimConfirmation(str(value).upper())
    except ValueError:
        return ClaimConfirmation.REPORTED


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    if args.limit < 1:
        raise SystemExit("--limit must be positive")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    mongo_client = MongoClient(os.getenv("FOOTBALLPULSE_MONGODB_URL", "mongodb://127.0.0.1:27017"))
    db = mongo_client[os.getenv("FOOTBALLPULSE_MONGODB_DB", "footballpulse")]
    engine = create_engine(database_url(), pool_pre_ping=True)
    stories = PostgresStoryRepository(engine)
    timelines = PostgresTimelineRepository(engine)
    revisions = PostgresEditorialRevisionRepository(engine)
    processed = 0
    skipped = 0
    now = datetime.now(UTC)

    query = {"validation_status": "VALIDATED", "valid_claims.0": {"$exists": True}}
    for enrichment in db.article_enrichments.find(query).sort("validated_at", 1).limit(args.limit):
        article_id = parse_uuid(enrichment.get("article_version_id"))
        if article_id is None:
            skipped += 1
            continue
        article = db.source_articles.find_one({"article_version_id": str(article_id)})
        intelligence = db.article_intelligence.find_one({"article_version_id": str(article_id)})
        if article is None or intelligence is None:
            LOGGER.warning("project_skipped_missing_input article_version_id=%s", article_id)
            skipped += 1
            continue
        entities = [item for item in intelligence.get("canonical_entities", []) if parse_uuid(item.get("entity_id"))]
        claims = [item for item in enrichment.get("valid_claims", []) if parse_uuid(item.get("subject_entity_id"))]
        if not entities or not claims:
            skipped += 1
            continue
        observed = article.get("published_at") or article.get("collected_at") or now
        if isinstance(observed, str):
            observed = datetime.fromisoformat(observed.replace("Z", "+00:00"))
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=UTC)
        story_id = stable(article_id, "story")
        source_link_id = stable(article_id, "source")
        story = Story.create(
            story_id=story_id,
            event_type=event_type(enrichment.get("event_type")),
            first_seen_at=observed,
            confidence_score=Decimal("0.6000"),
        )
        source = StorySource.create(
            link_id=source_link_id,
            story_id=story_id,
            article_version_id=article_id,
            source_id=UUID(str(article["source_id"])),
            source_reliability_tier=int(article.get("source_reliability_tier", 3)),
            published_at=observed,
            observed_at=observed,
        )
        story_entities = tuple(
            StoryEntity.create(
                link_id=stable(article_id, f"entity:{item['entity_id']}"),
                story_id=story_id,
                entity_id=UUID(str(item["entity_id"])),
                entity_type=EntityType(str(item["entity_type"]).upper()),
                now=observed,
            )
            for item in entities
        )
        claim_values: list[Claim] = []
        evidence_values: list[ClaimEvidence] = []
        content = str(article.get("cleaned_content", ""))
        for index, item in enumerate(claims):
            subject = parse_uuid(item.get("subject_entity_id"))
            if subject is None or not any(parse_uuid(e.get("entity_id")) == subject for e in entities):
                continue
            quote = str(item.get("evidence_quote", "")).strip()
            start = content.find(quote)
            if not quote or start < 0:
                continue
            claim_id = stable(article_id, f"claim:{index}")
            claim = Claim.create(
                claim_id=claim_id,
                story_id=story_id,
                subject_entity_id=subject,
                predicate=predicate(item.get("predicate")),
                object_entity_id=parse_uuid(item.get("object_entity_id")),
                object_value={"object_text": item.get("object_text"), "qualifiers": item.get("qualifiers", {})},
                statement_en=quote,
                certainty=Decimal("0.6000"),
                occurred_at=None,
                occurred_at_bucket=None,
                now=observed,
                confirmation=confirmation(item.get("certainty")),
            )
            claim_values.append(claim)
            evidence_values.append(ClaimEvidence.create(
                evidence_id=stable(article_id, f"evidence:{index}"),
                claim_id=claim_id,
                story_source_id=source_link_id,
                quote=quote,
                start=start,
                end=start + len(quote),
                now=observed,
            ))
        if not claim_values:
            skipped += 1
            continue
        event_id = stable(article_id, "event")
        created = stories.create_from_event(
            story=story,
            sources=(source,),
            entities=story_entities,
            claims=tuple(claim_values),
            evidence=tuple(evidence_values),
            processed_event=ProcessedEvent.create(
                record_id=stable(article_id, "processed"),
                consumer_name="validated-enrichment-projector-v1",
                event_id=event_id,
                event_type="article.enrichment.validated.v1",
                processed_at=now,
            ),
            outbox_events=(OutboxEvent.create(
                event_id=stable(article_id, "story-outbox"),
                aggregate_type="STORY",
                aggregate_id=story_id,
                event_type="story.created.v1",
                deduplication_key=f"story.created:{story_id}:1",
                payload={"story_id": str(story_id), "version": 1},
                now=now,
            ),),
        )
        summary_en = str(enrichment.get("validated_summary_en") or enrichment.get("summary_en") or "").strip()
        window = timeline_window_start(observed)
        timelines.add_once(TimelineEntry.create(
            entry_id=stable(article_id, "timeline"),
            story_id=story_id,
            window_start=window,
            summary_en=summary_en,
            summary_vi="Bản dịch tiếng Việt cần biên tập trước khi xuất bản.",
            confirmation=confirmation(claims[0].get("certainty")),
            used_claim_ids=tuple(claim.id for claim in claim_values),
            source_article_ids=(article_id,),
            created_at=now,
        ))
        generated_id = stable(article_id, "generated-article")
        if revisions.get_current(generated_id) is None:
            revisions.add(EditorialRevision.create(
                revision_id=stable(article_id, "revision-1"),
                generated_article_id=generated_id,
                story_id=story_id,
                story_version=1,
                revision_number=1,
                title_en=summary_en[:200],
                body_en=summary_en,
                title_vi="Bản tin cần biên tập tiếng Việt",
                body_vi="Bản dịch tiếng Việt cần biên tập trước khi xuất bản.",
                created_at=now,
            ))
        processed += 1
        LOGGER.info("enrichment_projected article_version_id=%s story_id=%s story_created=%s", article_id, story_id, created)
    engine.dispose()
    mongo_client.close()
    LOGGER.info("projection_completed processed=%s skipped=%s", processed, skipped)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
