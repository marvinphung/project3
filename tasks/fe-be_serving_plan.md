# Implementation Plan: FE-BE Serving Readiness

## Overview

Muc tieu la lam public frontend chay end-to-end dung boundary:

```text
Frontend -> Backend API -> PostgreSQL
```

Backend API khong doc MongoDB. Neu UI can data ma PostgreSQL chua co, can bo
sung PostgreSQL read model va update publisher de day data tu Mongo pipeline
store sang PostgreSQL. Plan nay dua tren Playwright audit ngay 2026-08-21 voi
frontend tai `http://192.168.1.4:8443`.

## Audit Findings

### Dang hoat dong

- Homepage `/` render duoc top 10 entities.
- `GET /api/v2/entities/top?limit=10&window=24h` tra `200`.
- Search `/tim-kiem?q=Arsenal` render duoc ket qua.
- `GET /api/v2/entities/search?q=Arsenal` tra `200`.
- PostgreSQL local co data co ban:
  - `entities`: 28 rows.
  - `entity_timeline_items`: 28 rows.
  - `timeline_item_articles`: 111 rows.
  - `source_articles`: 30 rows.

### Dang loi

- Entity detail `/entity/:id` hien `Không thể tải timeline entity`.
- Backend `GET /api/v2/entities/{id}/timeline` dang `500`.
- Root cause: SQL text dung `where tia.timeline_item_id in :item_ids`, psycopg
  render thanh `in $1`, sai cu phap PostgreSQL.
- Latest news `/tin-moi` hien API unavailable.
- Frontend goi `GET /api/v2/articles?limit=20`, backend chua co endpoint nay
  nen tra `404`.
- Entity directories `/clb`, `/cau-thu`, `/hlv` crash React Router.
- Backend `GET /api/v2/entities?type=...` tra schema moi:
  `canonical_name`, `mention_count_24h`.
- Frontend directory van doc schema cu:
  `entity.name`, `article_count`, `story_count`.
- Runtime error: `Cannot read properties of undefined (reading 'charAt')`.
- Footer links `gioi-thieu`, `nguon-tin`, `dieu-khoan`, `lien-he` chua co
  routes public tuong ung.

## Architecture Decisions

- Backend API la public serving boundary duy nhat cho frontend.
- Backend API chi doc PostgreSQL.
- Mongo chi la pipeline store cho crawler, entities-extraction,
  content-summary.
- Publisher la noi duy nhat copy/denormalize pipeline data sang PostgreSQL.
- Entity public contract can thong nhat quanh canonical entity:
  `id`, `entity_type`, `canonical_name`, `slug`, `aliases`,
  `mention_count_24h`, `last_seen_at`.
- Article public contract can du de list/detail article tu PostgreSQL.
- Trong dot nay uu tien public UX: home, search, entity detail, entity
  directories, latest news, article detail.
- Admin/editorial pages khong nam trong scope chinh, tru khi build hoac public
  route bi anh huong.

## Target API Contract

### Entity Endpoints

`GET /api/v2/entities/top?window=24h&limit=10`

- Return top canonical entities ranked by distinct article count in last 24h.
- Response fields: `id`, `entity_type`, `canonical_name`, `slug`, `aliases`,
  `mention_count_24h`, `last_seen_at`.

`GET /api/v2/entities/search?q=Arsenal`

- Search `canonical_name`, `slug`, and `aliases`.
- Empty result is valid: `{"items":[]}`.

`GET /api/v2/entities?type=CLUB&limit=100&offset=0&q=ars`

- Return same canonical entity summary shape as top/search.
- Include `limit`, `offset`, `total`.
- Type filter supports `PLAYER`, `CLUB`, `COACH`, `COMPETITION`.

`GET /api/v2/entities/{entity_id}`

- Return one canonical entity summary.
- Return `404` if missing.

`GET /api/v2/entities/{entity_id}/timeline?limit=50&offset=0`

- Return entity summary and timeline items newest first.
- Each timeline item includes `source_articles`.
- Keep `key_entities_50` and `key_entities_80` as compatibility arrays for now,
  but they may be empty under the new one-call summary strategy.

### Article Endpoints To Add

`GET /api/v2/articles?limit=20&offset=0&sort=newest&q=&entity_type=&entity_slug=&story_id=`

Minimum item fields:

- `id`
- `slug`
- `title_en`
- `title_vi`
- `excerpt_vi`
- `body_en`
- `body_vi`
- `story_id`
- `published_at`
- `entities`

Notes:

- Backed by PostgreSQL `source_articles`.
- `title_vi/body_vi` may initially reuse English content because current
  frontend expects Vietnamese field names.
- `entities` should be derived from:
  `timeline_item_articles -> entity_timeline_items -> entities`.
- `sort=newest` sorts by `coalesce(published_at, crawled_at) desc`.
- If no body exists yet in PostgreSQL, `body_vi` can temporarily fallback to
  `description`, but publisher must be updated to backfill body.

`GET /api/v2/articles/{id_or_slug}`

- Lookup by UUID id or `slug`.
- Return one public article using the same article item schema.
- Return `404` if missing.

`GET /api/v2/articles/{id_or_slug}/sources`

- Return source/provenance rows for ArticleDetailPage.
- For source articles, one row based on `source_articles` is acceptable.

## PostgreSQL Read Model Additions

Current `source_articles` has metadata but not guaranteed full content. Add
columns if missing:

- `slug text`
- `body text`
- `excerpt text`
- `language text not null default 'en'`

Recommended indexes:

- Unique index on `source_articles.slug` when not null.
- Index on `coalesce(published_at, crawled_at) desc`.
- Text search index on title/description/body if search is needed.

Do not make public frontend depend on old `articles/stories` tables. New public
article endpoints should prefer `source_articles` because it is populated by v2
publisher.

## Phase 1: Fix Existing Entity Serving Path

### Task 1: Fix timeline endpoint SQL

Description: Fix `GET /api/v2/entities/{entity_id}/timeline` so it can fetch
source articles for timeline items without SQL syntax errors.

Implementation notes:

- Likely files:
  - `services/api-gateway/src/footballpulse_api_gateway/api/public_v2.py`
  - `services/api-gateway/tests/test_public_v2_endpoints.py`
- Replace `where tia.timeline_item_id in :item_ids` with a SQLAlchemy-safe
  pattern:
  - preferred: `.bindparams(sa.bindparam("item_ids", expanding=True))`
  - or PostgreSQL `= any(:item_ids)` with typed UUID array.
- Keep response shape unchanged.

Acceptance criteria:

- [ ] `GET /api/v2/entities/{known_id}/timeline` returns `200`.
- [ ] Response has non-empty `items` for an entity that has timeline rows.
- [ ] Each item includes source articles when mappings exist.
- [ ] CORS header is present for `Origin: http://192.168.1.4:8443`.

Verification:

- [ ] `uv run pytest services/api-gateway/tests/test_public_v2_endpoints.py`
- [ ] Manual/API check in container for a known entity id.
- [ ] Playwright: click first top entity from homepage and confirm timeline
      renders.

Dependencies: None.

Estimated scope: Small.

### Task 2: Add regression coverage for timeline article lookup

Description: Ensure API tests catch future `IN :param` regressions for timeline
item article lookup.

Acceptance criteria:

- [ ] Test fixture contains at least one entity timeline item and one linked
      source article.
- [ ] Test asserts `source_articles.length === 1`.
- [ ] Test fails if the endpoint returns `500`.

Verification:

- [ ] `uv run pytest services/api-gateway/tests/test_public_v2_endpoints.py`

Dependencies: Task 1.

Estimated scope: Small.

## Phase 2: Make PostgreSQL Article Read Model Complete Enough

### Task 3: Add source article content fields to PostgreSQL schema

Description: Extend `source_articles` so public article list/detail can be
served from PostgreSQL only.

Implementation notes:

- Add migration/bootstrap schema code for `slug`, `body`, `excerpt`, `language`.
- Update SQLAlchemy table definitions if used:
  `services/api-gateway/src/footballpulse_api_gateway/persistence/public_tables.py`.
- Make schema changes idempotent for local dev.

Acceptance criteria:

- [ ] Fresh/local Postgres schema can be provisioned with these columns.
- [ ] Existing rows remain valid after migration.
- [ ] `source_articles.slug` can be populated idempotently.

Verification:

- [ ] `docker compose -f docker-compose.v2.yml exec -T postgres psql ... \d source_articles`
- [ ] Relevant schema tests if present.

Dependencies: None.

Estimated scope: Medium.

### Task 4: Update publisher to populate article body/excerpt/slug

Description: Publisher should copy enough article data from Mongo pipeline store
into PostgreSQL `source_articles` so backend API does not need Mongo.

Implementation notes:

- Likely files:
  - `services/publisher-service/src/footballpulse_publisher_service/publisher.py`
  - `services/publisher-service/tests/test_publisher.py`
- During `publish_summary`, load `news_content` for `article_ids`.
- Upsert into `source_articles`:
  - `slug`: stable slug from title + short article id suffix, or article UUID
    fallback.
  - `body`: `news_content.content`.
  - `excerpt`: `news_metadata.description` or first 240 chars of body.
  - `language`: `news_metadata.language` or `en`.
- Preserve idempotency.
- Do not overwrite good body with empty string.

Acceptance criteria:

- [ ] Published source articles include `slug`, `body`, `excerpt`, `language`.
- [ ] Re-running publisher does not duplicate rows.
- [ ] Existing timeline publishing remains intact.

Verification:

- [ ] `uv run pytest services/publisher-service/tests/test_publisher.py`
- [ ] `docker compose -f docker-compose.v2.yml run --rm publisher python -m footballpulse_pipeline publish --limit 100`
- [ ] SQL check: `select count(*) from source_articles where body is not null`.

Dependencies: Task 3.

Estimated scope: Medium.

### Task 5: Backfill existing local PostgreSQL article rows

Description: For already-published local data, run publisher/backfill so
`source_articles` rows have new fields. This is required for immediate local UI
testing.

Acceptance criteria:

- [ ] Existing `source_articles` rows have stable `slug`.
- [ ] At least timeline-linked articles have `body` or a safe fallback body.
- [ ] Backend can serve `/api/v2/articles` without reading Mongo.

Verification:

- [ ] SQL count before/after backfill.
- [ ] `GET /api/v2/articles?limit=3` returns article items with non-empty title
      and body/excerpt.

Dependencies: Task 4.

Estimated scope: Small.

## Phase 3: Add Article Public API

### Task 6: Implement `GET /api/v2/articles`

Description: Add public latest articles endpoint backed by PostgreSQL
`source_articles`.

Implementation notes:

- Likely files:
  - `services/api-gateway/src/footballpulse_api_gateway/api/public_v2.py`
  - `services/api-gateway/tests/test_public_v2_endpoints.py`
- Add Pydantic response model compatible with current frontend `V2Article`.
- Support `limit`, `offset`, `sort=newest|oldest`, optional `q`.
- Accept optional `entity_type`, `entity_slug`, `story_id`; implement filters if
  straightforward, otherwise return a valid response without crashing and note
  unsupported filters in tests/docs.

Acceptance criteria:

- [ ] `GET /api/v2/articles?limit=20` returns `200`.
- [ ] Response shape matches frontend `listArticles`.
- [ ] Items sorted newest by `coalesce(published_at, crawled_at)` by default.
- [ ] Empty DB returns `items: []`, not `500`.

Verification:

- [ ] `uv run pytest services/api-gateway/tests/test_public_v2_endpoints.py`
- [ ] API smoke via curl/container.

Dependencies: Task 3, Task 5 for rich local data.

Estimated scope: Medium.

### Task 7: Implement `GET /api/v2/articles/{id_or_slug}`

Description: Add article detail endpoint for `ArticleDetailPage`.

Acceptance criteria:

- [ ] Lookup by UUID id works.
- [ ] Lookup by slug works when slug exists.
- [ ] `404` for missing article.
- [ ] Response contains `title_vi`, `body_vi`, `published_at`, `entities`.

Verification:

- [ ] API endpoint tests.
- [ ] Open first article from `/tin-moi` in Playwright.

Dependencies: Task 6.

Estimated scope: Small.

### Task 8: Implement `GET /api/v2/articles/{id_or_slug}/sources`

Description: Provide source/provenance data for ArticleDetailPage using
PostgreSQL only.

Acceptance criteria:

- [ ] Endpoint returns `200` with `items`.
- [ ] For a source article, one item is enough:
      `source_id`, `source_name`, `source_url`, `published_at`,
      `reliability_tier`.
- [ ] `source_url` points to article URL/canonical URL.

Verification:

- [ ] API endpoint tests.
- [ ] Article detail page no longer shows API error for sources.

Dependencies: Task 7.

Estimated scope: Small.

### Task 9: Attach entities to article API responses

Description: Add article-level entities for cards/chips using PostgreSQL read
model joins.

Implementation notes:

- Derive entities from
  `timeline_item_articles -> entity_timeline_items -> entities`.
- Deduplicate per article/entity.
- Return fields expected by frontend adapters: `id`, `entity_type`, `name`,
  `slug`.

Acceptance criteria:

- [ ] Article list/detail includes deduplicated `entities`.
- [ ] Entity chips link to a working entity route.
- [ ] Missing entity joins produce `entities: []`, not an error.

Verification:

- [ ] API test with one article linked to one entity.
- [ ] Playwright `/tin-moi` shows article cards and optional entity chips.

Dependencies: Task 6.

Estimated scope: Medium.

## Phase 4: Align Frontend With Canonical Entity Contract

### Task 10: Update frontend entity types and adapters

Description: Replace old directory expectations (`name`, `article_count`,
`story_count`) with canonical entity summary fields returned by backend.

Implementation notes:

- Likely files:
  - `frontend/src/api/client.ts`
  - `frontend/src/api/models.ts`
  - `frontend/src/api/adapters.ts`
  - `frontend/src/pages/EntityDirectoryPage.tsx`
  - possibly `frontend/src/pages/ClubsPage.tsx`, `PlayersPage.tsx`,
    `CoachesPage.tsx` if still used.
- Prefer one canonical frontend type for public entity summary:
  `id`, `entity_type`, `canonical_name`, `slug`, `aliases`,
  `mention_count_24h`, `last_seen_at`.
- Directory pages should display `canonical_name`.
- Directory cards should link by entity id:
  `/clb/{id}`, `/cau-thu/{id}`, `/hlv/{id}`.

Acceptance criteria:

- [ ] `/clb` no longer crashes.
- [ ] `/cau-thu` no longer crashes.
- [ ] `/hlv` no longer crashes.
- [ ] Empty types show clear empty state.
- [ ] Existing home/search cards still render.

Verification:

- [ ] `npm run build` in `frontend`.
- [ ] Playwright directory audit.

Dependencies: Backend entity endpoints already available.

Estimated scope: Medium.

### Task 11: Remove or redirect stale entity pages/components

Description: The repo has overlapping pages with inconsistent route/link
behavior. Clean this up to avoid future regressions.

Acceptance criteria:

- [ ] Routes use one directory implementation per entity type.
- [ ] No public page links to stale slug-based detail route unless backend
      supports it.
- [ ] Build has no unused import/type failures.

Verification:

- [ ] `npm run build`.
- [ ] Playwright nav audit from header links.

Dependencies: Task 10.

Estimated scope: Small.

## Phase 5: Make Public News UX Work

### Task 12: Wire `/tin-moi` to the new article API

Description: Once backend article endpoints exist, ensure LatestNewsPage renders
actual source articles from PostgreSQL.

Acceptance criteria:

- [ ] `/tin-moi` renders article rows.
- [ ] No "API đang không khả dụng" when API returns `200`.
- [ ] `Xem thêm tin` increments limit and refetches.
- [ ] Filters that are not backed by API either work or are clearly neutral.

Verification:

- [ ] Playwright latest news audit.
- [ ] Browser console has no network/render errors for `/tin-moi`.

Dependencies: Tasks 6 and 9.

Estimated scope: Small.

### Task 13: Wire ArticleDetailPage to PostgreSQL article data

Description: Article detail should render from backend article endpoints backed
by PostgreSQL.

Acceptance criteria:

- [ ] Clicking a news row opens `/bai-viet/:id_or_slug`.
- [ ] Article detail renders title, body/excerpt fallback, source link.
- [ ] Missing story timeline does not crash ArticleDetailPage.
- [ ] If `story_id` is null, hide or gracefully empty the story timeline section.

Verification:

- [ ] Playwright clicks first `/tin-moi` article.
- [ ] No console errors on article detail.

Dependencies: Tasks 7 and 8.

Estimated scope: Medium.

## Phase 6: Route Hygiene And Static Public Links

### Task 14: Decide footer static pages

Description: Footer currently links to pages that do not exist:
`/gioi-thieu`, `/nguon-tin`, `/dieu-khoan`, `/lien-he`.

Recommended option: add minimal static pages for these links so public
navigation does not 404.

Alternative: remove footer links until pages exist.

Acceptance criteria:

- [ ] Clicking footer links does not show NotFound unless intentionally removed.
- [ ] Static pages have clear placeholder content and no API dependency.

Verification:

- [ ] Playwright footer link audit.

Dependencies: None.

Estimated scope: Small.

### Task 15: Normalize frontend API base URL for local/LAN testing

Description: Current frontend is served from `192.168.1.4:8443` but API base is
`localhost:8000`. This can work on same machine, but CORS and LAN testing are
fragile. Make local/prod behavior explicit.

Options:

- Preferred for dev: Vite proxy `/api -> http://localhost:8000`, set
  `VITE_API_BASE_URL=""`.
- Alternative: keep explicit `VITE_API_BASE_URL=http://localhost:8000` and keep
  backend CORS regex for local/LAN origins.

Acceptance criteria:

- [ ] Browser on `http://192.168.1.4:8443` can call all backend endpoints.
- [ ] `.env.example` documents the chosen local/prod config.
- [ ] Render/Vercel deployment can set explicit API URL.

Verification:

- [ ] Playwright audit from `http://192.168.1.4:8443`.
- [ ] API CORS header check for configured origins.

Dependencies: None.

Estimated scope: Small.

## Phase 7: Full UI Verification

### Task 16: Keep a Playwright smoke audit script

Description: Convert the temporary audit script into a committed smoke test or
script so regressions are easy to catch.

Implementation notes:

- Current temporary script path: `scripts/ui-audit.mjs`.
- Decide whether to keep it as `scripts/smoke-v2-ui.mjs` or a formal Playwright
  test under `frontend/tests`.

Acceptance criteria:

- [ ] Script checks home, search, entity detail, latest news, directories.
- [ ] Script reports failed requests and console errors.
- [ ] Script exits non-zero on critical regressions.

Verification:

- [ ] `node ../scripts/smoke-v2-ui.mjs` or equivalent.

Dependencies: Tasks 1-15.

Estimated scope: Small.

### Task 17: Run full serving verification

Description: Verify backend, frontend, and PostgreSQL read model together.

Acceptance criteria:

- [ ] Homepage renders 10 top entities.
- [ ] Clicking a top entity renders timeline.
- [ ] Searching `Arsenal` returns a result and click opens timeline.
- [ ] `/tin-moi` renders articles.
- [ ] Clicking a latest article renders detail.
- [ ] `/clb`, `/cau-thu`, `/hlv` do not crash.
- [ ] Browser console has no CORS/network/render errors for public pages.
- [ ] Backend logs have no `500` for audited public endpoints.

Verification:

- [ ] `uv run pytest services/api-gateway/tests/test_public_v2_endpoints.py`
- [ ] `uv run pytest services/publisher-service/tests/test_publisher.py`
- [ ] `npm run build` in `frontend`.
- [ ] Playwright smoke audit.
- [ ] `git diff --check`.

Dependencies: Tasks 1-16.

Estimated scope: Medium.

## Risks And Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| PostgreSQL local schema was manually patched and not reproducible | High | Add idempotent migration/bootstrap SQL and document it. |
| Article body not present in PostgreSQL | Medium | Publisher copies `news_content.content`; API falls back to description until backfill. |
| Old story/article UI conflicts with new entity timeline architecture | Medium | Keep compatibility endpoints minimal, then remove or hide unsupported story UI. |
| CORS works locally but fails on deploy | Medium | Make `FOOTBALLPULSE_API_CORS_ORIGINS` or regex explicit in `.env.example` and docs. |
| Frontend type drift recurs | Medium | Use one canonical entity response type and Playwright smoke audit. |

## Out Of Scope

- Reworking crawler/entities-extraction/content-summary logic.
- Admin/editorial workflow redesign.
- Full production migration strategy for historical old tables.
- New visual redesign beyond fixing broken public UX.

## Checkpoints

### Checkpoint A: Entity Timeline Usable

- [ ] Tasks 1-2 complete.
- [ ] Top entity click opens timeline with source articles.

### Checkpoint B: Latest News API Available

- [ ] Tasks 3-9 complete.
- [ ] `/api/v2/articles` and article detail endpoints return `200`.

### Checkpoint C: Frontend Contract Aligned

- [ ] Tasks 10-13 complete.
- [ ] Home, search, entity detail, latest news, directories work in browser.

### Checkpoint D: Ready For Deploy Prep

- [ ] Tasks 14-17 complete.
- [ ] Public UI smoke passes.
- [ ] Backend reads PostgreSQL only for public frontend data.
