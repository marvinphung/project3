# Implementation Plan: FootballPulse v2 Entity Timeline Pipeline

## Overview

Muc tieu la implement lai FootballPulse v2 theo kien truc da chot:

```text
Airflow-managed pipeline:
crawler -> entities-extraction -> content-summary -> publish

Serving layer:
backend-api -> frontend
```

MongoDB la pipeline store. Supabase PostgreSQL la serving read model day du cho
backend API va frontend; backend API khong doc Mongo.

Plan nay dung de giao cho Antigravity code theo tung phase. Khong coi backend
API va frontend la step trong Airflow flow; chung nam o serving layer va chi doc
du lieu sau publish.

## Confirmed Decisions

- Pipeline do Airflow quan ly gom `crawler`, `entities-extraction`,
  `content-summary`, `publish`.
- Timeline bucket co dinh 3 gio theo UTC.
- Moi canonical entity co timeline rieng.
- Entity types can support: `PLAYER`, `CLUB`, `COACH`, `COMPETITION`.
- Mongo giu raw/intermediate data: `news_metadata`, `news_content`,
  `canonical_entities`, `news_entities`, summary/timeline generation records.
- PostgreSQL giu read model day du: `entities`, `entity_timeline_items`,
  `timeline_item_articles`, `source_articles`.
- `entities-extraction-service` doc `clean_content`, tao `filtered_content`,
  roi extract entities tu `filtered_content`.
- Club aliases hien tai nam trong repo o
  `docs/europe_top6_clubs_2026_27_aliases.json` va duoc import vao Mongo
  `canonical_entities`.
- NER model dung model hien tai trong source, khong tao adapter/boundary moi.
- `content-summary-service` chay batch theo Airflow, khong event-driven theo
  tung article.
- Neu summary cho `entity + window_start + window_end` da ton tai thi skip.
- Ke ca window chi co 1 article van tao title va content.
- LLM prompts nam trong repo; provider/API/model nam trong `.env`.
- Khong can luu prompt/model/provider metadata vao DB.
- LLM dung `clean_content` lam article input.
- Frontend top 10 lay cac canonical entities xuat hien trong nhieu distinct
  articles nhat trong 24h; moi article tinh toi da 1 lan cho moi entity.
- Search entity tinh ca `canonical_name` va `aliases`, khong autocomplete. Neu
  khong tim thay thi hien "khong tim thay".

## Current Repo Context

Da co mot so nen tang can giu va hoan thien:

- `services/crawler-service`: crawl metadata va clean content vao Mongo.
- `services/entities-extraction-service`: xu ly backlog/Kafka `news.crawled.v1`
  va ghi `news_entities`.
- `services/publisher-service`: publisher cu dang publish theo
  `news_enrichments/stories/publications`, can doi sang entity timeline read
  model.
- `packages/pipeline/src/footballpulse_pipeline/cli.py`: co commands `crawl`,
  `process`, `publish`; can them `summary` hoac doi orchestration de co
  `content-summary`.
- `airflow/dags/footballpulse_crawl_v2.py`: crawl DAG trigger process DAG.
- `airflow/dags/footballpulse_process_v2.py`: process DAG hien trigger publish
  truc tiep; can chen summary DAG truoc publish.
- `supabase/migrations/202608180001_v2_product_schema.sql`: schema cu theo
  `stories/publications`, can redesign cho serving read model moi.
- `docs/version2/source-of-truth-entity-timeline-architecture.md`: source of
  truth architecture.
- Dang co worktree changes lien quan `canonical_entities`:
  - `docs/europe_top6_clubs_2026_27_aliases.json`
  - `docs/version2/mongo-canonical-entities-schema.md`
  - `scripts/import_canonical_entities.py`
  - `packages/mongo-models/src/footballpulse_mongo_models/documents.py`

Antigravity can doc cac thay doi nay va tiep tuc tu trang thai hien tai, khong
lam lai tu dau neu da dung huong.

## Target Data Model

### Mongo Pipeline Store

`news_metadata`

- `_id`: deterministic article UUID.
- URL/source/title/description/image/published_time/crawl_date/content_hash.

`news_content`

- `_id`: article UUID.
- `content`: clean content tu crawler.
- `filtered_content`: content sau khi replace aliases bang canonical names.
- `cleaned_at`, `filtered_at`, `extractor`, `extraction_status`.

`canonical_entities`

- Source of truth cho canonical club aliases va cac canonical entities da biet.
- Da co schema draft trong `docs/version2/mongo-canonical-entities-schema.md`.

`news_entities`

- `_id`: article UUID.
- `entities`: danh sach mentions/extracted entities.
- Moi entity mention nen co:
  - `label`: `PLAYER|CLUB|COACH|COMPETITION`.
  - `text`: extracted text tren `filtered_content`.
  - `score`, `start`, `end`.
  - `canonical_entity_id` neu match duoc.
  - `canonical_name` bat buoc cho grouping.
- `model_name`, `model_version`, `processed_at`.

`entity_timeline_summaries` hoac ten tuong duong

- `_id`: deterministic UUID tu `entity_id + window_start + window_end`.
- `entity_id`, `canonical_name`, `entity_type`.
- `window_start`, `window_end` UTC.
- `article_ids`: distinct article IDs trong window.
- `article_count`.
- `aggregated_news`: output LLM call 1.
- `short_description`: title/headline tu output LLM 1-call.
- `status`: `COMPLETED|FAILED|SKIPPED`.
- `created_at`, `updated_at`.

### PostgreSQL Serving Read Model

Redesign migration de PostgreSQL du data cho backend/frontend ma khong can Mongo:

`entities`

- `id uuid primary key`.
- `entity_type entity_type_v2 not null`.
- `canonical_name text not null`.
- `slug text not null`.
- `aliases text[] not null default '{}'`.
- `mention_count_24h integer not null default 0`.
- `last_seen_at timestamptz`.
- `metadata jsonb not null default '{}'`.
- `created_at`, `updated_at`.
- Unique: `(entity_type, slug)`.

`source_articles`

- `id uuid primary key`.
- `title text not null`.
- `url text not null`.
- `canonical_url text not null unique`.
- `source_name text not null`.
- `domain_name text not null`.
- `description text`.
- `image_url text`.
- `published_at timestamptz`.
- `crawled_at timestamptz not null`.
- `content_hash text`.
- `created_at`, `updated_at`.

`entity_timeline_items`

- `id uuid primary key`.
- `entity_id uuid not null references entities(id)`.
- `window_start timestamptz not null`.
- `window_end timestamptz not null`.
- `title text not null`.
- `summary text not null`.
- `article_count integer not null check (article_count > 0)`.
- `created_at`, `updated_at`.
- Unique: `(entity_id, window_start, window_end)`.

`timeline_item_articles`

- `timeline_item_id uuid references entity_timeline_items(id) on delete cascade`.
- `article_id uuid references source_articles(id) on delete cascade`.
- `position integer not null`.
- Primary key: `(timeline_item_id, article_id)`.

Recommended indexes:

- `entities (mention_count_24h desc, canonical_name asc)`.
- GIN/trigram or simple lower index for `canonical_name` and `aliases`.
- `entity_timeline_items (entity_id, window_start desc)`.
- `entity_timeline_items (window_start desc)`.
- `source_articles (published_at desc)`.
- `timeline_item_articles (article_id)`.

## API Contract Target

Backend API exposes minimum endpoints:

`GET /api/v2/entities/top?window=24h&limit=10`

- Returns top canonical entities ranked by distinct article count in last 24h.
- Each article contributes at most 1 count per entity.

`GET /api/v2/entities/search?q=...`

- Searches canonical name and aliases.
- No suggestions/autocomplete behavior required.
- Empty results are valid response, frontend renders not-found state.

`GET /api/v2/entities/{entity_id}/timeline`

- Returns timeline items newest first.
- Each item includes source articles.

Optional compatibility endpoints may remain only if frontend still needs them,
but new UI should move to the three endpoints above.

## Phase 1: Foundation And Schema Alignment

### Task 1: Update source-of-truth docs with corrected pipeline/serving boundary

Description: Fix docs so the architecture clearly says Airflow manages only
`crawler -> entities-extraction -> content-summary -> publish`; backend API and
frontend are serving layer, not pipeline stages.

Acceptance criteria:

- [ ] `docs/version2/source-of-truth-entity-timeline-architecture.md` separates
      Airflow pipeline from serving layer.
- [ ] Docs mention PostgreSQL serving read model is complete enough for API and
      frontend.
- [ ] Stale wording that says backend/frontend are flow steps is removed.

Verification:

- [ ] Manual docs review.

Dependencies: None.

Files likely touched:

- `docs/version2/source-of-truth-entity-timeline-architecture.md`
- `README.md`
- `docs/HUONG_DAN_CHAY.md`
- `docs/version2/local-development.md`

Estimated scope: S.

### Task 2: Finalize Mongo model for filtered content and timeline summaries

Description: Extend Mongo models/docs so entities extraction can persist
`filtered_content`, and content summary can persist per-entity per-window
summary records.

Acceptance criteria:

- [ ] `NewsContent` supports `filtered_content` and `filtered_at`.
- [ ] `NewsEntity` requires/stores canonical entity names for grouping.
- [ ] New Mongo document model exists for entity timeline summaries.
- [ ] Indexes support backlog/entity/window lookups.
- [ ] Docs describe `entity_timeline_summaries` or the chosen collection name.

Verification:

- [ ] Focused model tests updated or added if package tests exist.

Dependencies: Task 1.

Files likely touched:

- `packages/mongo-models/src/footballpulse_mongo_models/documents.py`
- `packages/mongo-models/src/footballpulse_mongo_models/__init__.py`
- `packages/mongo-models/tests/test_documents.py`
- `docs/version2/mongo-canonical-entities-schema.md`

Estimated scope: M.

### Task 3: Redesign PostgreSQL migration for entity timeline read model

Description: Replace or supersede the old `stories/publications` serving schema
with the confirmed tables: `entities`, `source_articles`,
`entity_timeline_items`, `timeline_item_articles`.

Acceptance criteria:

- [ ] Migration defines serving tables listed in Target Data Model.
- [ ] Old story/publication/claim tables are removed from target migration unless
      still needed by retained admin code.
- [ ] Entity aliases are queryable for search.
- [ ] Unique constraints support idempotent publish.
- [ ] Indexes support top 10, search, and entity timeline reads.

Verification:

- [ ] Migration can be applied to a fresh local PostgreSQL database.
- [ ] Schema review confirms backend API can satisfy target endpoints without
      Mongo.

Dependencies: Task 1.

Files likely touched:

- `supabase/migrations/202608180001_v2_product_schema.sql`
- `services/api-gateway/src/footballpulse_api_gateway/persistence/public_tables.py`
- DB docs under `docs/version2/`

Estimated scope: M.

## Checkpoint: Foundation

- [ ] Docs, Mongo models, and PostgreSQL schema agree on names and ownership.
- [ ] No code path requires backend API to read Mongo.
- [ ] Schema has natural idempotency keys for summary and publish.

## Phase 2: Entities Extraction

### Task 4: Implement canonical alias replacement inside entities-extraction-service

Description: Move canonicalization into `entities-extraction-service`. The
service reads `news_content.content`, loads active aliases from Mongo
`canonical_entities`, creates `filtered_content`, writes it back to
`news_content`, then runs existing NER on `filtered_content`.

Acceptance criteria:

- [ ] Crawler remains responsible only for clean content.
- [ ] `V2EntityProcessor.process_article` reads `content`.
- [ ] Alias map is built longest-match-first to avoid partial replacement bugs.
- [ ] Replacement is case-insensitive unless alias says `case_sensitive`.
- [ ] `filtered_content` and `filtered_at` are persisted before or with entity
      extraction.
- [ ] Existing NER model/runtime remains the model used.

Verification:

- [ ] Unit test for alias replacement edge cases.
- [ ] Unit test that `filtered_content` is used as extractor input.

Dependencies: Tasks 2 and canonical entity import script/data.

Files likely touched:

- `services/entities-extraction-service/src/footballpulse_entities_extraction_service/v2_processor.py`
- `services/entities-extraction-service/src/footballpulse_entities_extraction_service/domain/`
- `services/entities-extraction-service/tests/`
- `scripts/import_canonical_entities.py`

Estimated scope: M.

### Task 5: Canonicalize extracted entity output

Description: Ensure every extracted entity has grouping fields needed by summary
and publish. Club aliases should map to canonical club IDs/names. Other entity
types should still get stable canonical names from extraction text.

Acceptance criteria:

- [ ] Club mentions matching `canonical_entities` get `canonical_entity_id` and
      `canonical_name`.
- [ ] Player/coach/competition mentions get normalized canonical names even if
      no Mongo canonical entity exists yet.
- [ ] Per article, duplicate entity mentions do not cause duplicate article
      counts for ranking calculations.
- [ ] `news_entities` can be used to find all entities in an article without
      re-running NER.

Verification:

- [ ] Unit tests cover club alias match, unknown player fallback, and duplicate
      mention behavior.

Dependencies: Task 4.

Files likely touched:

- `services/entities-extraction-service/src/footballpulse_entities_extraction_service/v2_processor.py`
- `services/entities-extraction-service/src/footballpulse_entities_extraction_service/domain/extraction.py`
- `packages/mongo-models/src/footballpulse_mongo_models/documents.py`

Estimated scope: M.

## Checkpoint: Entities Extraction

- [ ] Articles with `news_metadata + news_content` and missing `news_entities`
      are processed.
- [ ] `news_content.filtered_content` is persisted.
- [ ] `news_entities` contains canonical names suitable for grouping.

## Phase 3: Content Summary Service

### Task 6: Scaffold content-summary-service

Description: Create `services/content-summary-service` as a new service package
installed into runtime image. It owns per-entity per-window summary generation.

Acceptance criteria:

- [ ] Service has `pyproject.toml`, package source, health/server entry if local
      pattern needs it, and domain/application modules.
- [ ] Runtime Dockerfile installs the service.
- [ ] `packages/pipeline` depends on the service package.
- [ ] Prompt files exist in repo under service-owned `prompts/`.
- [ ] LLM provider/API/model are loaded from `.env`.

Verification:

- [ ] Import check for service package.
- [ ] Docker/runtime install path review.

Dependencies: Tasks 2 and 3.

Files likely touched:

- `services/content-summary-service/`
- `services/runtime.Dockerfile`
- `packages/pipeline/pyproject.toml`
- `.env.example`

Estimated scope: M.

### Task 7: Implement UTC 3-hour window planning

Description: Add logic to compute fixed UTC 3-hour windows and select entities
that have at least one article in each window.

Acceptance criteria:

- [ ] Window boundaries are UTC and fixed at 00:00, 03:00, 06:00, etc.
- [ ] For each entity and window, service finds distinct article IDs containing
      that entity.
- [ ] If summary already exists for `entity_id + window_start + window_end`,
      service skips it.
- [ ] Window selection uses `news_metadata.crawl_date`.

Verification:

- [ ] Unit tests for window boundary calculation.
- [ ] Unit tests for skip-if-existing behavior.

Dependencies: Task 6.

Files likely touched:

- `services/content-summary-service/src/...`
- `services/content-summary-service/tests/`

Estimated scope: M.

### Task 8: Implement top-article selection for each entity/window

Description: For each entity/window article set, select the most relevant
articles before calling the LLM.

Acceptance criteria:

- [ ] Summary scope is limited to top 30 entities by distinct article count in
      the last 24h.
- [ ] Each article contributes at most one count per entity for top-30 ranking.
- [ ] For each entity/window, select at most 5 articles.
- [ ] Selection ranks by target entity mention count in `filtered_content`, then
      by newest `crawl_date`.

Verification:

- [ ] Unit tests for top-30 ranking and top-5 article selection.

Dependencies: Task 7.

Files likely touched:

- `services/content-summary-service/src/...`
- `services/content-summary-service/tests/`

Estimated scope: S.

### Task 9: Implement two-call LLM summary generation

Description: Generate timeline title and content using a prompt stored in repo.
Article input is selected `clean_content`, sorted newest first.

Acceptance criteria:

- [ ] LLM input includes at most 5 selected `clean_content` values newest first.
- [ ] LLM is called once per `entity + window`.
- [ ] LLM output includes `title` and `content`.
- [ ] `title` is stored as `short_description` for current read-model
      compatibility.
- [ ] `content` is stored as `aggregated_news`.
- [ ] Provider/API/model are configured from `.env`.
- [ ] No prompt/model/provider metadata is persisted unless needed for runtime
      error details.

Verification:

- [ ] Unit tests use fake LLM client.
- [ ] Prompt templates render deterministic inputs.

Dependencies: Task 8.

Files likely touched:

- `services/content-summary-service/src/...`
- `services/content-summary-service/prompts/`
- `.env.example`

Estimated scope: M.

### Task 10: Persist summary records idempotently

Description: Store completed summary/timeline records in Mongo with deterministic
ID or unique key by `entity_id + window_start + window_end`.

Acceptance criteria:

- [ ] Completed records include entity, window, selected article IDs,
      aggregated news/content, title, status, timestamps.
- [ ] Re-running the same window skips existing completed summaries.
- [ ] Failures are stored with enough error info for operations/debugging.
- [ ] No partial completed record is visible as publishable.

Verification:

- [ ] Unit/integration test with fake Mongo for completed, skipped, failed cases.

Dependencies: Task 9.

Files likely touched:

- `services/content-summary-service/src/...`
- `packages/mongo-models/src/footballpulse_mongo_models/documents.py`

Estimated scope: M.

## Checkpoint: Content Summary

- [ ] Running summary for a UTC window creates one Mongo summary per entity/window
      with at least one article.
- [ ] Summary uses `clean_content` but canonical entity lists.
- [ ] Existing summaries are skipped.

## Phase 4: Airflow And Pipeline CLI

### Task 11: Add pipeline CLI command for content summary

Description: Extend `footballpulse_pipeline` CLI with a `summary` command that
runs `content-summary-service` for one or more UTC windows.

Acceptance criteria:

- [ ] `python -m footballpulse_pipeline summary` exists.
- [ ] Command accepts explicit `--window-start`/`--window-end` or a "latest
      closed 3h window" mode.
- [ ] Command has a limit/batch control if needed.
- [ ] Command exits non-zero on fatal summary failures.

Verification:

- [ ] CLI parsing unit test or manual import/argparse check.

Dependencies: Task 10.

Files likely touched:

- `packages/pipeline/src/footballpulse_pipeline/cli.py`
- `packages/pipeline/pyproject.toml`

Estimated scope: S.

### Task 12: Update Airflow DAG chain

Description: Change orchestration from `crawl -> process -> publish` to
`crawl -> entities-extraction -> content-summary -> publish`.

Acceptance criteria:

- [ ] Process DAG no longer triggers publish directly.
- [ ] New summary DAG runs after entities extraction.
- [ ] Summary DAG triggers publish after completion.
- [ ] Docker compose Airflow env has `FOOTBALLPULSE_SUMMARY_COMMAND`.
- [ ] DAG names and task names clearly use `entities-extraction`, `summary`,
      `publish`.

Verification:

- [ ] Airflow DAG import/parsing check.

Dependencies: Task 11.

Files likely touched:

- `airflow/dags/footballpulse_process_v2.py`
- `airflow/dags/footballpulse_summary_v2.py`
- `airflow/dags/footballpulse_publish_v2.py`
- `docker-compose.v2.yml`
- `airflow/README.md`

Estimated scope: M.

### Task 13: Add docker-compose service for content-summary

Description: Add runnable `content-summary` service to local compose stack.

Acceptance criteria:

- [ ] `docker-compose.v2.yml` has `content-summary` service.
- [ ] Service uses runtime image and required Mongo/Postgres/LLM env.
- [ ] Service command runs pipeline summary command.
- [ ] Existing `entities-extraction` and `publisher` commands remain separate.

Verification:

- [ ] Compose config review.

Dependencies: Tasks 6 and 11.

Files likely touched:

- `docker-compose.v2.yml`
- `.env.example`
- `services/runtime.Dockerfile`

Estimated scope: S.

## Checkpoint: Orchestration

- [ ] Airflow DAG order is crawler, entities extraction, content summary,
      publish.
- [ ] Backend API/frontend are not part of Airflow flow.
- [ ] All runtime envs required by LLM and DB are documented.

## Phase 5: Publisher

### Task 14: Replace old article enrichment publisher with entity timeline publisher

Description: Update `publisher-service` so it publishes Mongo summary records to
PostgreSQL read model instead of old `news_enrichments/stories/publications`.

Acceptance criteria:

- [ ] Publisher reads completed Mongo entity timeline summaries.
- [ ] Publisher upserts `entities`.
- [ ] Publisher upserts `source_articles` for source metadata.
- [ ] Publisher upserts `entity_timeline_items`.
- [ ] Publisher upserts `timeline_item_articles` in newest-first article order.
- [ ] Publisher marks Mongo summary as published only after DB transaction
      succeeds.

Verification:

- [ ] Unit/integration test with test Postgres or SQL assertions.

Dependencies: Tasks 3 and 10.

Files likely touched:

- `services/publisher-service/src/footballpulse_publisher_service/publisher.py`
- `scripts/smoke-v2-publisher.py`
- `packages/pipeline/src/footballpulse_pipeline/cli.py`

Estimated scope: M.

### Task 15: Compute and publish 24h entity popularity

Description: Ensure PostgreSQL `entities.mention_count_24h` or equivalent
readable score reflects distinct article count in the last 24h.

Acceptance criteria:

- [ ] Popularity score counts distinct source articles per canonical entity.
- [ ] Each article contributes at most once per entity.
- [ ] Score updates during publish or via deterministic refresh query.
- [ ] Top endpoint can serve top 10 without Mongo.

Verification:

- [ ] Test data proves 15 mentions in one article count as 1.

Dependencies: Task 14.

Files likely touched:

- `services/publisher-service/src/footballpulse_publisher_service/publisher.py`
- `supabase/migrations/202608180001_v2_product_schema.sql`

Estimated scope: S.

## Checkpoint: Publish

- [ ] Fresh publish can materialize timeline data into PostgreSQL.
- [ ] Incremental publish only publishes new completed summary records.
- [ ] Backend API can serve required reads from PostgreSQL only.

## Phase 6: Backend API

### Task 16: Replace public API with entity timeline endpoints

Description: Update FastAPI public v2 routes to expose the target endpoints and
drop old story/publication assumptions from the serving API.

Acceptance criteria:

- [ ] `GET /api/v2/entities/top?window=24h&limit=10` returns top canonical
      entities by distinct article count.
- [ ] `GET /api/v2/entities/search?q=...` searches canonical name and aliases.
- [ ] `GET /api/v2/entities/{entity_id}/timeline` returns timeline items newest
      first with source articles.
- [ ] Empty search result returns 200 with empty items, not error.
- [ ] No route implementation reads Mongo.

Verification:

- [ ] API tests for top, search hit, search miss, timeline.

Dependencies: Tasks 3 and 14.

Files likely touched:

- `services/api-gateway/src/footballpulse_api_gateway/api/public_v2.py`
- `services/api-gateway/src/footballpulse_api_gateway/runtime_v2.py`
- `services/api-gateway/tests/`

Estimated scope: M.

### Task 17: Remove stale admin/editorial frontend/API dependencies if still present

Description: Current frontend client still references removed admin/editorial
endpoints. Clean these paths if they are outside target architecture or not
served by backend.

Acceptance criteria:

- [ ] Frontend does not call deleted `/admin/v1/editorial/*` or publish article
      endpoints.
- [ ] Routes/pages that depend on removed APIs are removed or isolated behind
      retained crawler source admin functionality.
- [ ] Backend tests do not expect removed admin/editorial APIs.

Verification:

- [ ] Typecheck/build catches no references to removed client functions.

Dependencies: Task 16.

Files likely touched:

- `frontend/src/api/client.ts`
- `frontend/src/routes.tsx`
- `frontend/src/pages/admin/*`
- `services/api-gateway/tests/`

Estimated scope: M.

## Checkpoint: Backend API

- [ ] Backend API is a pure PostgreSQL reader.
- [ ] Frontend-facing endpoints match the agreed contract.
- [ ] Removed legacy routes are not referenced by frontend.

## Phase 7: Frontend

### Task 18: Update frontend API client and models

Description: Replace old article/story client types with entity timeline types
that match backend API.

Acceptance criteria:

- [ ] Client has functions for top entities, entity search, entity timeline.
- [ ] Types model canonical entity, timeline item, and source article.
- [ ] Search miss is represented cleanly for UI.

Verification:

- [ ] Frontend typecheck/build.

Dependencies: Task 16.

Files likely touched:

- `frontend/src/api/client.ts`
- `frontend/src/api/models.ts`
- `frontend/src/api/hooks.ts`

Estimated scope: S.

### Task 19: Implement top entities and search UX

Description: Update UI so homepage or main entity surface shows top 10 entities
in last 24h, and search by canonical name/alias opens the entity timeline or
shows not-found.

Acceptance criteria:

- [ ] Top 10 entities are visible and sorted by 24h article count.
- [ ] Search uses backend endpoint and has no autocomplete UI.
- [ ] Search by alias can find canonical entity.
- [ ] Search miss shows "khong tim thay" state.

Verification:

- [ ] Frontend build/typecheck.
- [ ] Manual browser check when backend has seeded data.

Dependencies: Task 18.

Files likely touched:

- `frontend/src/pages/HomePage.tsx`
- `frontend/src/pages/SearchPage.tsx`
- `frontend/src/components/*`

Estimated scope: M.

### Task 20: Implement entity timeline page

Description: Update entity detail page to render timeline items for one entity,
newest first, with title/short description, aggregated summary, window time, and
source articles.

Acceptance criteria:

- [ ] Entity timeline route uses `entity_id` or a stable route that resolves to
      entity ID.
- [ ] Timeline items are sorted newest first.
- [ ] Each item shows short description/title and summary.
- [ ] Source articles are visible enough for users to inspect provenance.
- [ ] Empty timeline state is handled.

Verification:

- [ ] Frontend build/typecheck.
- [ ] Manual browser check with sample published data.

Dependencies: Task 18.

Files likely touched:

- `frontend/src/pages/EntityDetailPage.tsx`
- `frontend/src/components/StoryTimeline.tsx` or replacement component
- `frontend/src/routes.tsx`

Estimated scope: M.

## Checkpoint: Frontend

- [ ] User can see top 10 canonical entities.
- [ ] User can search by canonical name or alias.
- [ ] User can open a timeline for any entity with published data.

## Phase 8: Docs, Scripts, And Smoke Fixtures

### Task 21: Update docs and env examples

Description: Keep docs aligned with final implementation and remove stale
article/story/enrichment wording.

Acceptance criteria:

- [ ] Docs describe Airflow pipeline and separate serving layer.
- [ ] Env docs include LLM provider/API/model for content-summary.
- [ ] Docs mention Mongo collections and PostgreSQL read tables.
- [ ] No docs describe `ai-content-service`, `intelligence-service`,
      `news_enrichments`, or story/publication pipeline as target architecture.

Verification:

- [ ] `rg` review for stale terms.

Dependencies: All implementation phases or update incrementally.

Files likely touched:

- `README.md`
- `.env.example`
- `docs/HUONG_DAN_CHAY.md`
- `docs/version2/*`
- `airflow/README.md`

Estimated scope: S.

### Task 22: Update smoke scripts and fixtures

Description: Align smoke scripts with new end-to-end flow and sample data.

Acceptance criteria:

- [ ] Smoke sequence is crawl, entities extraction, content summary, publish,
      API.
- [ ] Existing smoke processor script validates `filtered_content` and
      `news_entities`.
- [ ] New smoke summary script can run with fake/mock LLM or clearly documented
      real LLM env.
- [ ] Publisher smoke validates PostgreSQL read model tables.

Verification:

- [ ] Smoke scripts pass when dependencies and env are available.

Dependencies: Tasks 4, 10, 14, 16.

Files likely touched:

- `scripts/smoke-v2-full-flow.sh`
- `scripts/smoke-v2-processor.py`
- `scripts/smoke-v2-publisher.py`
- `scripts/smoke-v2-summary.py`
- `tests/fixtures/*`

Estimated scope: M.

## Final Verification Checklist

Antigravity should run these after implementation, adjusted to actual repo
commands:

- [ ] Python unit tests for touched packages/services.
- [ ] API tests for public v2 endpoints.
- [ ] Frontend typecheck/build.
- [ ] Migration apply on fresh local PostgreSQL.
- [ ] Docker compose config validates.
- [ ] Airflow DAGs import successfully.
- [ ] End-to-end smoke flow with mock/fake LLM if real API is not configured.

## Risks And Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Alias replacement corrupts normal text | Medium | Use word-boundary/longest-match-first matching and tests for aliases like `City`, `United`, `FC`. |
| Canonical entity IDs for non-club entities are unstable | High | Define deterministic UUID from `entity_type + normalized canonical_name` when no canonical Mongo entity exists. |
| Window selection uses wrong timestamp | Medium | Use `crawl_date` consistently for summary buckets. |
| LLM cost grows because every entity/window with 1 article is summarized | Medium | Keep batch limits and explicit window command args; log article_count per generated item. |
| PostgreSQL migration breaks old frontend pages | Medium | Migrate frontend/API in same phase set and remove stale story/publication assumptions. |
| Publish duplicates timeline items | High | Enforce unique `(entity_id, window_start, window_end)` and transactional upserts. |
| Search alias semantics differ between Mongo and PostgreSQL | Medium | Publish aliases from canonical entities into PostgreSQL `entities.aliases` and test alias search. |

## Suggested Implementation Order

1. Docs/source-of-truth correction.
2. Mongo model finalization.
3. PostgreSQL schema redesign.
4. Entities extraction canonicalization and `filtered_content`.
5. Content summary service.
6. Pipeline CLI and Airflow DAG chain.
7. Publisher read model.
8. Backend API endpoints.
9. Frontend integration.
10. Docs/smoke script cleanup.

## Open Questions For Later

- Exact LLM provider env names and model name values.
- Exact prompt text for the two LLM calls.
- Whether old frontend admin source-management UI is still in scope long term.
- Whether PostgreSQL migration should be destructive local-only or additive for
  an existing Supabase environment.
