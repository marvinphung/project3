# Refactor Implementation Plan

## Overview

Plan nay bien thiet ke version 2 thanh cac task refactor co thu tu. Target
architecture:

```text
Local:
Airflow -> crawler -> Mongo -> Kafka news.crawled.v1
Kafka news.crawled.v1 -> processor -> Mongo -> Kafka news.enriched.v1
Kafka news.enriched.v1 -> publisher -> Supabase PostgreSQL

Production:
Vercel frontend -> Render backend-api -> Supabase PostgreSQL
```

MongoDB local luu du lieu crawl/xu ly theo schema `news_*`. Supabase PostgreSQL
luu product schema cho API/UI. Frontend khong hien pipeline flow. Backend Render
khong connect Mongo, Kafka, Airflow, Kaggle, GLiNER, hoac local pipeline.

## Architecture Decisions

- Giu Kafka va Airflow trong local pipeline, dua chung ra khoi production FE/BE.
- Dung `_id = article_id = uuid5(canonical_news_url)` cho tat ca Mongo collection
  va Supabase `articles.id`.
- Dung Mongo Beanie/Motor/Pydantic giong `news-aggregator`.
- Crawler moi run check toi da 500 URL candidate moi source, dedupe truoc fetch.
- Pipeline chay 100% tu dong, khong co human review step giua crawl/process/publish.
- Worker pool xu ly song song ben trong crawler, processor, Kaggle adapter, va
  publisher; Airflow khong tao task tung article.
- Kaggle dataset gom toan bo article chua co validated enrichment trong moi lan
  upload, khong luu `batch_id` vao DB.
- Backend API chi doc Supabase PostgreSQL va expose `/api/v1`.
- Khong luu log, batch state, job state, outbox, processed events trong DB schema
  chinh.

## Phase 1: Shared Identity And Models

### Task 1: Create Shared URL Identity Package

**Description:** Tao package shared nho cho URL canonicalization va deterministic
article ID. Day la dependency cua crawler, processor, publisher, va API tests.

**Acceptance criteria:**

- [ ] Co `canonicalize_news_url(url: str) -> str`.
- [ ] Co `article_id_from_url(url: str) -> UUID`.
- [ ] Cung URL voi tracking params/fragment khong tao article ID khac.
- [ ] Invalid URL bi reject ro rang.

**Verification:**

- [ ] Unit tests cover lowercase host, fragment removal, `utm_*` removal, sorted query.
- [ ] `uv run pytest` cho package/task lien quan pass.

**Dependencies:** None

**Files likely touched:**

- `packages/shared/`
- `tests/`

**Estimated scope:** Small

### Task 2: Create Mongo Beanie Models

**Description:** Tao package Mongo models version 2 theo `docs/version2/proposed-db-schema.md`.

**Acceptance criteria:**

- [ ] Co Beanie `Document` cho `news_metadata`, `news_content`,
  `news_entities`, `news_enrichments`.
- [ ] `news_embeddings` la optional model.
- [ ] ID dung `uuid.UUID`, khong dung ObjectId mac dinh.
- [ ] Indexes toi thieu duoc khai bao/bootstrapped.

**Verification:**

- [ ] Unit tests validate model serialization/deserialization.
- [ ] Integration smoke voi Mongo local neu co compose running.

**Dependencies:** Task 1

**Files likely touched:**

- `packages/mongo-models/`
- `tests/`

**Estimated scope:** Medium

### Task 3: Create Supabase Schema Package And Migration

**Description:** Tao migration SQL/Supabase model cho product schema version 2.

**Acceptance criteria:**

- [ ] Migration tao cac bang: `sources`, `articles`, `entities`,
  `entity_aliases`, `stories`, `story_entities`, `story_sources`, `claims`,
  `timeline_entries`, `publications`.
- [ ] `articles.id` dung UUID tu Mongo article ID.
- [ ] Unique keys/indexes dung theo schema da chot.
- [ ] Khong tao bang log/batch/job/outbox.

**Verification:**

- [ ] Migration apply duoc tren Postgres local hoac Supabase branch.
- [ ] Basic insert/select tests cho cac bang core pass.

**Dependencies:** Task 1

**Files likely touched:**

- `packages/supabase-models/`
- `supabase/migrations/` hoac migration folder tuong duong
- `tests/`

**Estimated scope:** Medium

### Checkpoint: Foundation

- [ ] Shared identity tests pass.
- [ ] Mongo models import duoc.
- [ ] Supabase schema apply duoc.
- [ ] Khong co code production backend import Mongo/Kafka/Airflow.

## Phase 2: Local Crawler And Kafka Handoff

### Task 4: Refactor Crawler To Write V2 Mongo Collections

**Description:** Chuyen crawler local sang flow crawl RSS/article, tao article ID,
ghi `news_metadata` va `news_content`.

**Acceptance criteria:**

- [ ] Crawler doc RSS source config local.
- [ ] Moi source check toi da 500 URL candidate moi scheduled run.
- [ ] Moi URL tao `_id = uuid5(canonical_news_url)`.
- [ ] Duplicate URL canonical bi skip bang lookup `_id` truoc khi fetch HTML.
- [ ] Scheduled mode fetch toi da 100 bai moi/source/run.
- [ ] Bootstrap mode co the fetch toi da 500 bai moi/source/run.
- [ ] Crawler co global concurrency va per-domain concurrency cap.
- [ ] Crawler ghi du `news_metadata` va `news_content`.
- [ ] Raw HTML khong luu DB.

**Verification:**

- [ ] Unit tests cho URL/source parsing.
- [ ] Unit tests cover dedupe-before-fetch.
- [ ] Unit tests cover scheduled/bootstrap crawl limit.
- [ ] Fixture crawl test ghi dung Mongo docs.
- [ ] Manual local run crawl duoc mot source mock.

**Dependencies:** Tasks 1, 2

**Files likely touched:**

- `pipeline/crawler/`
- `packages/shared/`
- `packages/mongo-models/`
- `tests/`

**Estimated scope:** Medium

### Task 5: Add Kafka `news.crawled.v1` Producer

**Description:** Sau khi crawler ghi Mongo thanh cong, publish pointer event nhe
vao Kafka.

**Acceptance criteria:**

- [ ] Topic `news.crawled.v1` co DTO/version ro.
- [ ] Event chi chua `article_id`, `canonical_url`, `source_name`, `published_time`.
- [ ] Full content khong dua vao Kafka.
- [ ] Producer chi publish sau khi Mongo write thanh cong.

**Verification:**

- [ ] Unit tests validate event payload.
- [ ] Kafka integration smoke publish/consume duoc event.

**Dependencies:** Task 4

**Files likely touched:**

- `pipeline/crawler/`
- `packages/shared/`
- `tests/`

**Estimated scope:** Small

### Task 6: Create Airflow Crawl DAG

**Description:** Tao/sua Airflow DAG de schedule crawler local. DAG chi goi
pipeline command, khong chua logic crawl tung article.

**Acceptance criteria:**

- [ ] DAG `footballpulse_crawl` schedule duoc.
- [ ] Schedule mac dinh `*/30 * * * *`.
- [ ] DAG dung `catchup=False`.
- [ ] DAG dung `max_active_runs=1`.
- [ ] DAG goi crawler command voi env local.
- [ ] DAG khong import Mongo models/business logic truc tiep neu khong can.
- [ ] DAG khong ghi batch/job state vao DB product.

**Verification:**

- [ ] Airflow DAG import test pass.
- [ ] Manual trigger local goi crawler command duoc.

**Dependencies:** Task 5

**Files likely touched:**

- `airflow/dags/`
- `airflow/tests/`

**Estimated scope:** Small

### Checkpoint: Crawler

- [ ] Running crawler tao Mongo `news_metadata/news_content`.
- [ ] Kafka co event `news.crawled.v1`.
- [ ] Airflow import DAG clean.

## Phase 3: Processor And Enrichment

### Task 7: Refactor Processor To Consume `news.crawled.v1`

**Description:** Processor consume Kafka event, doc Mongo theo `article_id`, chay
entity extraction/enrichment, va ghi Mongo processed collections.

**Acceptance criteria:**

- [ ] Processor consume `news.crawled.v1`.
- [ ] Processor co fallback scan Mongo cho manual replay.
- [ ] Processor extract entities song song theo article voi configurable
  `entity_workers`.
- [ ] Processor ghi `news_entities`.
- [ ] Processor ghi `news_enrichments` khi validation pass.
- [ ] AI failure khong ghi raw model output vao DB.
- [ ] Validation fail khong publish `news.enriched.v1` va khong tao review queue.

**Verification:**

- [ ] Unit tests cho selection/fallback scan.
- [ ] Unit tests cho automated validation gate.
- [ ] Fixture event -> processed Mongo docs pass.

**Dependencies:** Tasks 2, 5

**Files likely touched:**

- `pipeline/processor/`
- `packages/mongo-models/`
- `tests/`

**Estimated scope:** Medium

### Task 8: Keep Kaggle Adapter Behind Processor Boundary

**Description:** Giu pattern Kaggle tu `news-aggregator`: prepare input dataset,
push kernel, poll status, download output. Adapter nam trong local processor,
khong trong BE API.

**Acceptance criteria:**

- [ ] Processor co provider interface cho enrichment.
- [ ] Kaggle provider build `articles.jsonl` tu toan bo article co content nhung
  chua co validated enrichment.
- [ ] Kaggle provider implement dataset upload -> kernel push -> poll -> output.
- [ ] Kaggle run artifacts nam trong local temp folder, khong ghi `batch_id` vao DB.
- [ ] Local/mock provider co the dung cho test.
- [ ] Output validate truoc khi ghi `news_enrichments`.

**Verification:**

- [ ] Contract tests cho provider output.
- [ ] Kaggle command builder tests khong can network.
- [ ] Fixture backlog nhieu article tao dung `articles.jsonl`.

**Dependencies:** Task 7

**Files likely touched:**

- `pipeline/processor/`
- `kaggle/`
- `tests/`

**Estimated scope:** Medium

### Task 9: Add Kafka `news.enriched.v1` Producer

**Description:** Sau khi enrichment validated va ghi Mongo, publish pointer event
cho publisher.

**Acceptance criteria:**

- [ ] Topic `news.enriched.v1` co DTO/version ro.
- [ ] Event chi chua `article_id`, `event_type`, `validation_status`, `processed_at`.
- [ ] Producer chi publish khi `validation_status = VALIDATED`.

**Verification:**

- [ ] Unit tests validate event payload.
- [ ] Kafka integration smoke publish/consume duoc event.

**Dependencies:** Task 7

**Files likely touched:**

- `pipeline/processor/`
- `tests/`

**Estimated scope:** Small

### Task 10: Create Airflow Process DAG

**Description:** Tao/sua Airflow DAG de run processor local sau crawl schedule.

**Acceptance criteria:**

- [ ] DAG `footballpulse_process` goi processor command.
- [ ] DAG co the chay theo schedule hoac trigger sau crawl.
- [ ] Fallback schedule mac dinh `*/30 * * * *`.
- [ ] DAG dung `catchup=False`.
- [ ] DAG dung `max_active_runs=1`.
- [ ] DAG khong chua AI/business logic tung article.

**Verification:**

- [ ] Airflow DAG import test pass.
- [ ] Manual trigger local goi processor command duoc.

**Dependencies:** Task 9

**Files likely touched:**

- `airflow/dags/`
- `airflow/tests/`

**Estimated scope:** Small

### Checkpoint: Processor

- [ ] Kafka `news.crawled.v1` -> processor -> Mongo `news_enrichments`.
- [ ] Kafka `news.enriched.v1` duoc publish.
- [ ] Airflow process DAG import clean.

## Phase 4: Publisher To Supabase

### Task 11: Implement Publisher Article/Source Upsert

**Description:** Publisher consume `news.enriched.v1`, doc Mongo, va upsert
`sources`, `articles` vao Supabase.

**Acceptance criteria:**

- [ ] Publisher consume Kafka va co fallback scan Mongo.
- [ ] Chi publish article co validated enrichment.
- [ ] Publisher upsert song song voi configurable `publisher_workers`.
- [ ] `articles.id = Mongo _id`.
- [ ] Upsert idempotent theo `sources.domain_name` va `articles.id`.

**Verification:**

- [ ] Integration test voi Postgres local.
- [ ] Running publisher 2 lan khong tao duplicate.

**Dependencies:** Tasks 3, 9

**Files likely touched:**

- `pipeline/publisher/`
- `packages/supabase-models/`
- `packages/mongo-models/`
- `tests/`

**Estimated scope:** Medium

### Task 12: Implement Publisher Entity/Story Upsert

**Description:** Tao/match entities va stories tu `news_entities/news_enrichments`.

**Acceptance criteria:**

- [ ] Entities upsert theo `(entity_type, slug)`.
- [ ] Entity aliases upsert theo `normalized_alias`.
- [ ] Story matching MVP deterministic.
- [ ] `story_entities` va `story_sources` idempotent.

**Verification:**

- [ ] Tests cho story matching deterministic.
- [ ] Running publisher 2 lan khong duplicate relationships.

**Dependencies:** Task 11

**Files likely touched:**

- `pipeline/publisher/`
- `packages/supabase-models/`
- `tests/`

**Estimated scope:** Medium

### Task 13: Implement Publisher Claims/Timeline/Publications

**Description:** Sync validated claims va tao timeline/publication records de UI
co data doc ngay tu Supabase.

**Acceptance criteria:**

- [ ] Claims upsert idempotent theo stable claim ID.
- [ ] Timeline entries upsert idempotent theo stable timeline ID.
- [ ] Publications tao khi co du title/body/summary.
- [ ] Khong ghi pipeline flow/status vao Supabase.

**Verification:**

- [ ] Tests cho claim/timeline ID stability.
- [ ] API fixture query duoc timeline/publication sau publish.

**Dependencies:** Task 12

**Files likely touched:**

- `pipeline/publisher/`
- `packages/supabase-models/`
- `tests/`

**Estimated scope:** Medium

### Task 14: Create Airflow Publish DAG

**Description:** Tao/sua Airflow DAG de run publisher local sau processor.

**Acceptance criteria:**

- [ ] DAG `footballpulse_publish` goi publisher command.
- [ ] DAG trigger sau process va co fallback schedule `*/15 * * * *`.
- [ ] DAG dung `catchup=False`.
- [ ] DAG dung `max_active_runs=1`.
- [ ] DAG khong connect frontend/backend production.
- [ ] DAG khong ghi batch/job state vao DB product.

**Verification:**

- [ ] Airflow DAG import test pass.
- [ ] Manual trigger local sync duoc fixture len Postgres/Supabase test.

**Dependencies:** Task 13

**Files likely touched:**

- `airflow/dags/`
- `airflow/tests/`

**Estimated scope:** Small

### Checkpoint: Publisher

- [ ] Mongo validated enrichment -> Supabase product rows.
- [ ] Publisher idempotent.
- [ ] FE-required tables co data.

## Phase 5: Backend API

### Task 15: Create `apps/backend-api`

**Description:** Tach backend API production moi chi doc Supabase PostgreSQL.

**Acceptance criteria:**

- [ ] App FastAPI co `/health`.
- [ ] App config CORS theo env.
- [ ] App chi co Supabase/Postgres repository.
- [ ] Khong import Mongo/Kafka/Airflow/Kaggle packages.

**Verification:**

- [ ] Unit tests import app pass.
- [ ] `/health` test pass.

**Dependencies:** Task 3

**Files likely touched:**

- `apps/backend-api/`
- `tests/`

**Estimated scope:** Small

### Task 16: Implement Articles And Stories APIs

**Description:** Implement endpoints dau tien theo `proposed-api-contract.md`.

**Acceptance criteria:**

- [ ] `GET /api/v1/articles`.
- [ ] `GET /api/v1/articles/{id}`.
- [ ] `GET /api/v1/stories`.
- [ ] `GET /api/v1/stories/{id}`.
- [ ] Pagination va error envelope thong nhat.

**Verification:**

- [ ] API tests voi seeded Postgres pass.
- [ ] OpenAPI sinh dung response schemas.

**Dependencies:** Task 15

**Files likely touched:**

- `apps/backend-api/`
- `packages/supabase-models/`
- `tests/`

**Estimated scope:** Medium

### Task 17: Implement Timeline, Entities, Publications, Search APIs

**Description:** Hoan thien API surface cho FE.

**Acceptance criteria:**

- [ ] Story timeline endpoint.
- [ ] Entity list/detail/timeline endpoints.
- [ ] Publications list/detail endpoints.
- [ ] Search endpoint.
- [ ] Khong co endpoint pipeline/batch/job.

**Verification:**

- [ ] API tests voi seeded Postgres pass.
- [ ] Basic smoke query tat ca endpoint pass.

**Dependencies:** Task 16

**Files likely touched:**

- `apps/backend-api/`
- `packages/supabase-models/`
- `tests/`

**Estimated scope:** Medium

### Checkpoint: Backend

- [ ] Backend API chay local.
- [ ] Tat ca endpoint FE can co data tu Supabase.
- [ ] Khong co Mongo/Kafka/Airflow dependency trong backend production.

## Phase 6: Frontend

### Task 18: Move Frontend To `apps/frontend`

**Description:** Di chuyen frontend hien tai sang folder target va giu app build
duoc.

**Acceptance criteria:**

- [ ] Frontend nam tai `apps/frontend`.
- [ ] Vite config/build path dung.
- [ ] Env `VITE_BACKEND_API_URL` duoc dung.

**Verification:**

- [ ] `npm install`/`pnpm install` theo package manager chon.
- [ ] `npm run build` hoac equivalent pass.

**Dependencies:** None, but safer after API contract

**Files likely touched:**

- `apps/frontend/`
- `frontend/`
- config root

**Estimated scope:** Medium

### Task 19: Replace Frontend API Client With V2 Contract

**Description:** Chuyen FE sang goi `apps/backend-api` theo contract moi.

**Acceptance criteria:**

- [ ] FE khong query Supabase truc tiep.
- [ ] FE khong hien pipeline/batch/job/crawl status.
- [ ] Pages doc articles/stories/entities/timeline/publications tu BE API.
- [ ] Error/loading state van hoat dong.

**Verification:**

- [ ] Frontend build pass.
- [ ] Browser smoke voi backend local pass.

**Dependencies:** Tasks 16, 17, 18

**Files likely touched:**

- `apps/frontend/src/api/`
- `apps/frontend/src/pages/`
- `apps/frontend/src/components/`

**Estimated scope:** Medium

### Checkpoint: Frontend

- [ ] FE local hien data tu backend local.
- [ ] FE khong co pipeline UI.
- [ ] FE ready for Vercel env config.

## Phase 7: Deployment And Cleanup

### Task 20: Add Render Backend Deployment Config

**Description:** Them config deploy Render cho `apps/backend-api`.

**Acceptance criteria:**

- [ ] Start command ro rang.
- [ ] Env vars documented.
- [ ] Health check path `/health`.

**Verification:**

- [ ] Backend starts locally with production-like env.
- [ ] Render config reviewed.

**Dependencies:** Task 17

**Files likely touched:**

- `apps/backend-api/`
- `render.yaml` optional
- `docs/version2/`

**Estimated scope:** Small

### Task 21: Add Vercel Frontend Deployment Config

**Description:** Them config deploy Vercel cho `apps/frontend`.

**Acceptance criteria:**

- [ ] Build command ro rang.
- [ ] Output dir ro rang.
- [ ] `VITE_BACKEND_API_URL` documented.

**Verification:**

- [ ] Frontend production build pass.
- [ ] Vercel config reviewed.

**Dependencies:** Task 19

**Files likely touched:**

- `apps/frontend/`
- `vercel.json` optional
- `docs/version2/`

**Estimated scope:** Small

### Task 22: Remove Or Isolate V1-Only Runtime Code

**Description:** Sau khi V2 path da chay, don cac code khong con trong target:
multi-service internal HTTP mesh, outbox DB state, processed events DB state,
batch/job-state DB.

**Acceptance criteria:**

- [ ] Code V1 khong con duoc import boi V2 apps/pipeline.
- [ ] Docs version1 van giu lich su thiet ke cu.
- [ ] README/local commands tro ve V2 path.

**Verification:**

- [ ] Full focused test suite pass.
- [ ] `rg` confirms backend API has no Mongo/Kafka/Airflow/Kaggle imports.
- [ ] Manual local flow crawl/process/publish/API/FE works.

**Dependencies:** Tasks 14, 17, 19

**Files likely touched:**

- old `services/`
- root config
- docs

**Estimated scope:** Large, split further when reached

### Final Checkpoint

- [ ] Airflow local can run crawl/process/publish.
- [ ] Kafka topics carry pointer events only.
- [ ] Mongo has `news_*` documents.
- [ ] Publisher syncs validated records to Supabase.
- [ ] Backend Render app reads only Supabase.
- [ ] Frontend Vercel app calls only backend API.
- [ ] No pipeline flow/status UI.

## Risks And Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Refactor qua rong mot lan | High | Lam theo phases va checkpoint |
| Story matching MVP qua don gian | Medium | Dung deterministic key truoc, nang cap sau bang embedding |
| Supabase schema doi trong khi FE dang refactor | Medium | Chot API contract va response DTO truoc |
| Kafka consumer replay lam duplicate | Medium | Dung `article_id` va Supabase unique keys de idempotent |
| Kaggle integration cham/khong on dinh | Medium | Giu local/mock provider cho tests va fallback manual |

## Open Questions

- Co can `publications` ngay trong MVP hay timeline/articles la du truoc?
- Entity seed ban dau lay tu file local hay tao truc tiep trong Supabase?
- Airflow nen co 3 DAG rieng hay 1 DAG tong `crawl -> process -> publish`?
- Backend API co can admin/editor auth trong V2 dau tien khong, hay chi public read?
