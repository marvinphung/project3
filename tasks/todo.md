# FootballPulse v2 Implementation Todo

## Phase 1: Foundation And Schema Alignment

- [x] Task 1: Update source-of-truth docs with corrected pipeline/serving boundary.
- [x] Task 2: Finalize Mongo model for filtered content and timeline summaries.
- [x] Task 3: Redesign PostgreSQL migration for entity timeline read model.
- [x] Checkpoint: Docs, Mongo models, and PostgreSQL schema agree.

## Phase 2: Entities Extraction

- [x] Task 4: Implement canonical alias replacement inside entities-extraction-service.
- [x] Task 5: Canonicalize extracted entity output.
- [x] Checkpoint: `filtered_content` and canonical `news_entities` are persisted.

## Phase 3: Content Summary Service

- [x] Task 6: Scaffold content-summary-service.
- [x] Task 7: Implement UTC 3-hour window planning.
- [x] Task 8: Implement entity frequency threshold calculation.
- [x] Task 9: Implement two-call LLM summary generation.
- [x] Task 10: Persist summary records idempotently.
- [x] Checkpoint: Summary records exist per entity/window and skip existing rows.

## Phase 4: Airflow And Pipeline CLI

- [x] Task 11: Add pipeline CLI command for content summary.
- [x] Task 12: Update Airflow DAG chain.
- [x] Task 13: Add docker-compose service for content-summary.
- [x] Checkpoint: Airflow order is crawler, entities extraction, content summary, publish.

## Phase 5: Publisher

- [x] Task 14: Replace old article enrichment publisher with entity timeline publisher.
- [x] Task 15: Compute and publish 24h entity popularity.
- [x] Checkpoint: PostgreSQL read model is populated without backend Mongo reads.

## Phase 6: Backend API

- [x] Task 16: Replace public API with entity timeline endpoints.
- [x] Task 17: Remove stale admin/editorial frontend/API dependencies if still present.
- [x] Checkpoint: API exposes top entities, search, and entity timeline.

## Phase 7: Frontend

- [x] Task 18: Update frontend API client and models.
- [x] Task 19: Implement top entities and search UX.
- [x] Task 20: Implement entity timeline page.
- [x] Checkpoint: User can view top entities, search, and open entity timeline.

## Phase 8: Docs, Scripts, And Smoke Fixtures

- [x] Task 21: Update run scripts, seed scripts, and smoke fixtures.
- [x] Task 22: Update developer documentation and diagrams.
- [x] Checkpoint: Full test suite passes; smoke pipeline script runs locally.
