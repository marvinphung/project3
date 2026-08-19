# Local Real-data Admin UI Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task.

**Goal:** Chạy FootballPulse tại localhost với mọi route admin dùng API và database thật; không route nào fallback về fixture/mock hoặc để action click im lặng.

**Architecture:** React chỉ gọi API Gateway/Crawler qua typed client. API Gateway tạo read model bị giới hạn từ PostgreSQL/MongoDB cho dashboard, Story, publication và lỗi; Crawler vẫn sở hữu source mutation. Frontend không query database và endpoint list có pagination thống nhất.

**Tech Stack:** React/Vite/TypeScript, FastAPI/Pydantic, SQLAlchemy/PostgreSQL, PyMongo/MongoDB, Docker Compose, pytest, pnpm.

---

## Non-goals

- Không thêm TLS, cloud, HA, backup, CI/CD hoặc thay topology Docker local.
- Không bypass `NEEDS_CONTENT_REVIEW`, không tự publish và không thay đổi model/pipeline AI.
- `auto_approve_drafts` để phase sau: chỉ bắt đầu khi luồng revision thật, audit và UI setting đã có dữ liệu chính xác.

## Contract chung

Mọi list admin mới dùng shape:

```json
{ "items": [], "total": 0, "limit": 50, "offset": 0, "next_offset": null }
```

`limit` trong 1..100, `offset >= 0`; filter là query string. Response lỗi giữ envelope đang dùng. API không trả raw HTML/source content ở list.

## Baseline đã hoàn thành

- `GET /admin/v1/source-articles` và `AdminArticlesPage` dùng MongoDB thật.
- `GET /admin/v1/operations/summary` và `AdminDashboard` dùng MongoDB/PostgreSQL thật; activity fixture không còn render.
- `AdminSourcesPage` dùng list/create/update/toggle/crawl của Crawler API; không fallback source fixture.

## Task 1 — Khóa dashboard và sources bằng test/API smoke

**Files:**
- Modify: `services/api-gateway/tests/test_editorial_admin_api.py`
- Modify: `frontend/src/pages/admin/AdminDashboard.tsx`
- Modify: `frontend/src/pages/admin/AdminSourcesPage.tsx`

1. Chạy focused gateway test để chốt response summary/source article hiện có.

   ```bash
   uv run pytest services/api-gateway/tests/test_editorial_admin_api.py -q
   ```

2. Chạy frontend build để khóa typed client/dashboard/sources.

   ```bash
   corepack pnpm --dir frontend build
   ```

3. Sau khi Docker build, login admin và xác nhận dashboard có count database thật; source list không render BBC/Sky fixture khi API trả empty/error.

4. Commit riêng phần dashboard/sources sau khi test xanh.

## Task 2 — Pagination và filter thật cho editorial draft

**Files:**
- Modify: `services/api-gateway/src/footballpulse_api_gateway/api/editorial_admin.py`
- Modify: `services/api-gateway/src/footballpulse_api_gateway/application/editorial_admin_adapter.py`
- Modify: `services/content-service/src/footballpulse_content_service/editorial/repository.py`
- Modify: `services/content-service/src/footballpulse_content_service/editorial/postgres_repository.py`
- Modify: `services/api-gateway/tests/test_editorial_admin_api.py`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/pages/admin/AdminDraftPage.tsx`

1. Write failing API test for `GET /admin/v1/editorial/revisions?state=NEEDS_REVIEW&limit=50&offset=0`; assert list envelope, total and no other states.
2. Run focused test; expect failure because current endpoint returns a bare capped array.
3. Add repository method `list_current_page(limit, offset, state)` and `count_current(state)` using SQL filter/order by `updated_at DESC`; preserve the existing bare method only until all callers migrate.
4. Change API to `EditorialRevisionListResponse`; validate `state` from known enum and return `next_offset`.
5. Add typed client `listEditorialRevisions({ state, limit, offset })`; replace draft page’s implicit 100 limit with tabs/counts and Next/Previous. Keep mutation actions untouched and reload the same filter/page after success.
6. Run:

   ```bash
   uv run pytest services/api-gateway/tests/test_editorial_admin_api.py -q
   corepack pnpm --dir frontend build
   ```

7. Commit: `feat: paginate real editorial revisions`.

**Acceptance:** Dashboard draft count equals the sum of real `DRAFT` and `NEEDS_REVIEW`; Draft page shows only server-filtered records and a truthful empty state.

## Task 3 — Story read model and UI

**Files:**
- Create: `services/api-gateway/src/footballpulse_api_gateway/persistence/admin_story_read_repository.py`
- Modify: `services/api-gateway/src/footballpulse_api_gateway/api/editorial_admin.py`
- Modify: `services/api-gateway/src/footballpulse_api_gateway/runtime_v2.py`
- Modify: `services/api-gateway/tests/test_editorial_admin_api.py`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/pages/admin/AdminStoryPage.tsx`

1. Write failing API test for `GET /admin/v1/stories?limit=50&offset=0&status=...`, using an in-memory repository fake. Contract item: `id`, `event_type`, `status`, `confidence_score`, `version`, `first_seen_at`, `last_seen_at`, `source_count`.
2. Add `AdminStoryView`, `AdminStoryPage`, Pydantic response and `AdminStoryReadRepository` protocol. Endpoint is editor-authenticated.
3. Implement PostgreSQL query against `intelligence_schema.stories`, left-join/aggregate `story_sources`, order by `last_seen_at DESC`, add optional status filter, total query and bounds.
4. Wire repository in `runtime_v2.py`; test API fake and repository query mapping.
5. Add `listAdminStories` client function and replace the `stories` constant/filter buttons with server state. “Xem” only links to an existing detail route; otherwise remove it and show the list honestly.
6. Run focused API tests and frontend build; commit `feat: show real admin stories`.

**Acceptance:** Story count/list comes from PostgreSQL; an empty database renders “Chưa có Story” rather than four transfer fixtures.

## Task 4 — Publication read model and UI

**Files:**
- Create: `services/api-gateway/src/footballpulse_api_gateway/persistence/admin_publication_read_repository.py`
- Modify: `services/api-gateway/src/footballpulse_api_gateway/api/editorial_admin.py`
- Modify: `services/api-gateway/src/footballpulse_api_gateway/runtime_v2.py`
- Modify: `services/api-gateway/tests/test_editorial_admin_api.py`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/pages/admin/AdminPublishedPage.tsx`

1. Write failing API test for `GET /admin/v1/publications?limit=50&offset=0` expecting admin-authenticated list envelope.
2. Add `PublicationListView`/protocol and SQL repository from `content_schema.publications`, ordered `published_at DESC`; item has only persisted fields (`id`, `slug`, `title_vi`, `story_id`, `published_at`).
3. Add endpoint/client. Do not invent editor name, page view count or unpublish behavior because the schema has none.
4. Replace `usePublicArticles(50)` and placeholder actions. “Xem public” links `/tin/{slug}` only when public route exists; render no edit/unpublish button until a command API exists.
5. Run focused API tests/build; commit `feat: list real admin publications`.

**Acceptance:** Published page reflects exactly persisted publications, including the current small real total; no fake views/editor values remain.

## Task 5 — Failure read model and errors UI

**Files:**
- Create: `services/api-gateway/src/footballpulse_api_gateway/persistence/processing_failure_read_repository.py`
- Modify: `services/api-gateway/src/footballpulse_api_gateway/api/editorial_admin.py`
- Modify: `services/api-gateway/src/footballpulse_api_gateway/runtime_v2.py`
- Modify: `services/api-gateway/tests/test_editorial_admin_api.py`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/pages/admin/AdminErrorsPage.tsx`

1. Inspect persisted failure sources before coding: Mongo `ai_batch_jobs` terminal failures/partial results and PostgreSQL `content_schema.publication_outbox` with `state`/`last_error`.
2. Write failing test for `GET /admin/v1/processing-failures?limit=50&offset=0`, fake repository and normalized item `id`, `stage`, `status`, `message`, `occurred_at`, `retryable`.
3. Implement a bounded union read model. Prefix IDs with owner (`ai:`/`publication:`), redact raw payload/content, sort descending and provide accurate total.
4. Do **not** render Retry/Ignore buttons until each owner exposes a safe real command. Page initially is read-only with stage/status and empty state.
5. Replace three fixture errors with `listProcessingFailures`; add loading/error/empty views.
6. Run focused API tests/build; commit `feat: show persisted processing failures`.

**Acceptance:** Errors page is accurate even if it is empty; it never claims an arbitrary crawler timeout happened.

## Task 6 — Remove residual admin fixture behavior

**Files:**
- Modify: `frontend/src/pages/admin/AdminDashboard.tsx`
- Modify: `frontend/src/pages/admin/AdminSourcesPage.tsx`
- Modify: `frontend/src/pages/admin/AdminStoryPage.tsx`
- Modify: `frontend/src/pages/admin/AdminPublishedPage.tsx`
- Modify: `frontend/src/pages/admin/AdminErrorsPage.tsx`
- Modify: `frontend/src/pages/admin/AdminDraftPage.tsx`

1. Run audit:

   ```bash
   rg -n "data/mock|sourcesData|const stories =|const recent =|247|1,842|Lỗi crawl: marca" frontend/src/pages/admin
   ```

2. For each remaining occurrence, either replace with typed API result or delete the control/content. Do not add placeholder sample records.
3. Verify every list has loading, API error and empty state; every active button makes a real request.
4. Run frontend build and `git diff --check`; commit `refactor: remove admin fixture fallbacks`.

## Task 7 — Local end-to-end acceptance

**Files:** no product code unless a verified defect is found.

1. Rebuild the services affected by the final API changes and frontend:

   ```bash
   docker compose --profile core --profile app build api-gateway frontend
   docker compose --profile core --profile app up -d --force-recreate api-gateway frontend
   docker compose --profile core --profile app ps
   ```

2. Verify API with an authenticated localhost request (token never printed in logs/user output): dashboard, source articles, drafts, stories, publications and failures all return their declared contract.
3. In browser, login and visit every admin route. Verify Network has real `/admin/v1/*`/crawler requests, no console errors, counts match database response, and an empty/error response is rendered honestly.
4. Final test gate:

   ```bash
   uv run pytest services/api-gateway/tests services/crawler-service/tests -q
   corepack pnpm --dir frontend build
   git diff --check
   ```

5. Record the actual result and remaining intentionally unsupported mutations in `docs/final-handoff.md`.

## Task 8 — Remove all public entity fixture routes

**Files:**
- Modify: `frontend/src/pages/PlayersPage.tsx`
- Modify: `frontend/src/pages/ClubsPage.tsx`
- Modify: `frontend/src/pages/CoachesPage.tsx`
- Modify: `frontend/src/pages/PlayerDetailPage.tsx`
- Modify: `frontend/src/pages/ClubDetailPage.tsx`
- Modify: `frontend/src/pages/CoachDetailPage.tsx`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/hooks.ts`
- Modify: `services/api-gateway/src/footballpulse_api_gateway/api/public.py` only if the existing entity/article contract lacks required query fields
- Modify: `services/api-gateway/tests/test_public_api.py`

1. Write/extend public API tests for entity list by `type`/`q` and related publication list by `entity_type`/`entity_slug`; assert database-empty behavior is an empty list, not sample values.
2. Run the test first. If an existing endpoint already returns `id`, `name`, `slug`, `story_count`, `article_count`, reuse it; add only fields that are actually persisted. Do not create a profile-image, club, league, country, position or crest API from fictional fixture data.
3. Add hooks with `loading`, `error`, and `data`; replace all `../data/mock` imports. Entity links use canonical slug, never a fallback first record.
4. Render entity detail with canonical entity data, `StoryTimeline`, and `listArticles({ entityType, entitySlug })`; sidebar/related sections use the same real article result or render empty state.
5. Remove “nổi bật”, pseudo profile metadata and “Xem thêm” controls when no backend-supported ranking/metadata/pagination exists; retain only API-backed controls.
6. Run:

   ```bash
   uv run pytest services/api-gateway/tests/test_public_api.py -q
   corepack pnpm --dir frontend build
   rg -n "data/mock" frontend/src
   ```

7. Commit `refactor: replace public entity fixtures with api data`.

## Definition of Done

- Dashboard, Sources, Source Articles, Stories, Drafts, Publications and Errors all call real APIs.
- No admin fixture/fallback survives production routes.
- Lists with more than 100 possible records use server pagination; counts are database-derived.
- UI has explicit loading/error/empty states and no silent action.
- Focused/full local tests, frontend build, Compose smoke and browser API inspection have fresh passing evidence.
- `rg "data/mock" frontend/src` returns no production route imports.
