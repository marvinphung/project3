# Kế hoạch API và mapping frontend

## 1. Quy ước chung

- Base path: `/api/v1`.
- JSON fields: `camelCase`; DB/event: `snake_case`.
- ID là opaque string; URL public ưu tiên `slug`.
- List response:

```json
{
  "data": [],
  "pagination": {
    "page": 1,
    "pageSize": 20,
    "totalItems": 0,
    "totalPages": 0
  }
}
```

- Default `page=1`, `pageSize=20`, max `pageSize=100`; stable sort có ID
  tie-breaker. Cursor pagination là P1.
- Error envelope thống nhất được định nghĩa trong `architecture.md`.
- Mutation nhận `Idempotency-Key` khi có side effect retryable; optimistic
  mutation nhận `expectedVersion`.
- Auth roles: `PUBLIC`, `EDITOR`, `PUBLISHER`, `ADMIN`.
- Rate limit là planned default, phải config được và xác nhận qua test:
  public GET 120/min/IP; search 60/min/IP; login 10/15min/IP; admin GET
  120/min/user; command 10/min/user; generate/crawl/publish 5/min/user.

Gateway dùng public read models cho public GET và dashboard summaries; command
được route một hop tới owning service. Không tạo chuỗi Gateway → service A →
service B cho page load.

## 2. Shared response schemas

- `EntitySummary`: `id`, `slug`, `type`, `name`, optional current club/country,
  article count, featured fields.
- `NewsSummary`: `id`, `slug`, headline, summary, `publishedAt`,
  `sourceCount`, confirmation display status, entities, cover image placeholder.
- `NewsDetail`: summary + body blocks, story ref, timeline, source references,
  related news.
- `StoryDetail`: ID/slug, working title, category, confirmation, status,
  version, entities, source count, timeline, latest article.
- `CommandAccepted`: command ID, resource ID, status, correlation ID.
- `VersionedResource`: `version`, `updatedAt`.

Cover image là placeholder/local asset trong MVP; không crawl/reuse source
images.

## 3. Public API catalog

| Endpoint | Query/body → response | Rate/auth | Owner | UI hiện có |
| --- | --- | --- | --- | --- |
| `GET /news` | `page,pageSize,status,entityId,sort`; `Paginated<NewsSummary>` | 120/min, PUBLIC | Gateway read model | `/`, `/tin-moi` |
| `GET /news/{slug}` | `NewsDetail` | 120/min, PUBLIC | Gateway read model | `/bai-viet/:id` |
| `GET /stories/{idOrSlug}` | `StoryDetail` | 120/min, PUBLIC | Gateway read model | Route story **chưa có**, planned |
| `GET /players` | `q,featured,hasRecentNews,page`; entity list | 120/min, PUBLIC | Gateway read model | `/cau-thu` |
| `GET /players/{slug}` | entity detail + recent news + active stories | 120/min | Gateway read model | `/cau-thu/:id` |
| `GET /clubs` | như players | 120/min | Gateway read model | `/clb` |
| `GET /clubs/{slug}` | club detail + articles/related entities | 120/min | Gateway read model | `/clb/:id` |
| `GET /coaches` | như players | 120/min | Gateway read model | `/hlv` |
| `GET /coaches/{slug}` | coach detail + articles | 120/min | Gateway read model | `/hlv/:id` |
| `GET /search` | required `q` 2–100 chars; optional `type,page,pageSize`; grouped hoặc paged results | 60/min | Gateway search read model | Header, `/tim-kiem` |

Search response `type=ALL`:

```json
{
  "query": "man",
  "groups": {
    "news": [],
    "stories": [],
    "players": [],
    "clubs": [],
    "coaches": []
  },
  "aliasesMatched": ["Man Utd"]
}
```

Public article chỉ trả source name, original title, publication time và original
URL; không trả raw body. Story timeline là editorial representation, không phải
technical log.

## 4. Admin/API command catalog

### Authentication

| Endpoint | Body → response | Role/rate | Errors | Owner/idempotency |
| --- | --- | --- | --- | --- |
| `POST /auth/login` | `{email,password}` → access token + refresh session | anonymous, 10/15min | `INVALID_CREDENTIALS`, `ACCOUNT_DISABLED`, `RATE_LIMITED` | Gateway; không idempotency |
| `POST /auth/refresh` | refresh cookie/token → new access | authenticated session | invalid/revoked/expired | Gateway; rotate token |
| `POST /auth/logout` | session ID → 204 | any auth | 401 | Gateway; idempotent |

### Sources và crawl

| Endpoint | Body/response | Role/rate | Idempotency/errors | Owner |
| --- | --- | --- | --- | --- |
| `GET /admin/sources` | filters + paginated source configs | ADMIN 120/min | — | Crawler |
| `POST /admin/sources` | name/type/URL/allowlist/rate/timeout/parser config → source | ADMIN 20/min | `Idempotency-Key`; duplicate, unsafe URL, validation | Crawler |
| `PATCH /admin/sources/{id}` | partial fields + `expectedVersion` → source | ADMIN 20/min | 409 version conflict; unsafe URL | Crawler |
| `POST /admin/sources/{id}/crawl` | `{mode:"NORMAL",from?,to?}` → `CommandAccepted` | ADMIN 5/min | key required; disabled/paused/conflict | Crawler |
| `GET /admin/crawl-runs` | status/source/date pagination | ADMIN | — | Crawler |
| `GET /admin/crawl-runs/{id}` | batch + attempts/counters/errors | ADMIN | not found | Crawler |

### Source articles

| Endpoint | Body/response | Role/rate | Idempotency/errors | Owner |
| --- | --- | --- | --- | --- |
| `GET /admin/source-articles` | source/status/duplicate/date/story filters | EDITOR | — | Article via Gateway |
| `GET /admin/source-articles/{id}` | evidence metadata, preview, duplicate, history | EDITOR | not found | Article |
| `POST /admin/source-articles/{id}/reprocess` | `{targetStage,reason}` → accepted | EDITOR 10/min | key; invalid stage/in progress | Article |
| `POST /admin/source-articles/{id}/story-assignment` | `{storyId,reason,expectedStoryVersion}` | EDITOR 20/min | key; story/version conflict | Intelligence |
| `PATCH /admin/source-articles/{id}/entities` | correction list + reason | EDITOR 20/min | version conflict/unknown entity | Intelligence |

Gateway không query Mongo trực tiếp; nó proxy một hop tới Article internal API.

### Stories

| Endpoint | Body/response | Role/rate | Idempotency/errors | Owner |
| --- | --- | --- | --- | --- |
| `GET /admin/stories` | status/category/confirmation/review filters | EDITOR | — | Intelligence |
| `GET /admin/stories/{id}` | story, candidates, sources, claims, timeline, versions | EDITOR | not found | Intelligence |
| `POST /admin/stories/{id}/merge` | `{sourceStoryId,expectedTargetVersion,expectedSourceVersion,reason}` | EDITOR 10/min | key; conflict/cycle/already merged | Intelligence |
| `POST /admin/stories/{id}/articles` | `{sourceArticleId,expectedVersion,reason}` | EDITOR 20/min | key; assigned elsewhere/conflict | Intelligence |
| `DELETE /admin/stories/{id}/articles/{articleId}` | `{targetStoryId?,reason,expectedVersion}` | EDITOR | key; invariant violation | Intelligence |
| `POST /admin/stories/{id}/generate` | `{expectedVersion,promptVersion?}` | EDITOR 5/min | key; no claims/stale version/already queued | Intelligence → Kafka |

### Draft/editorial/publication

| Endpoint | Body/response | Role/rate | Idempotency/errors | Owner |
| --- | --- | --- | --- | --- |
| `GET /admin/drafts` | status/story/date pagination | EDITOR | — | Content |
| `GET /admin/drafts/{id}` | draft, current revision, sources/claims/warnings/history | EDITOR | not found | Content |
| `PATCH /admin/drafts/{id}` | headline/summary/body/entities + `expectedVersion` | EDITOR 30/min | conflict/unsupported source ref | Content |
| `POST /admin/drafts/{id}/regenerate` | `{expectedVersion,instructions?}` | EDITOR 5/min | key; in progress/stale story | Content command → Kafka |
| `POST /admin/drafts/{id}/approve` | `{revisionId,expectedVersion,note?}` | EDITOR 10/min | key; validation warning/conflict | Content |
| `POST /admin/drafts/{id}/reject` | `{revisionId,expectedVersion,reason}` | EDITOR 10/min | key; invalid transition | Content |
| `POST /admin/drafts/{id}/publish` | `{revisionId,expectedVersion}` | PUBLISHER 5/min | key required; not approved/stale/already published | Content |
| `GET /admin/publications` | date/status pagination | EDITOR | — | Content |

`SCHEDULED`/schedule endpoints không thuộc MVP.

### Failure operations

| Endpoint | Body/response | Role/rate | Idempotency/errors | Owner |
| --- | --- | --- | --- | --- |
| `GET /admin/failures` | service/stage/class/status/date filters | ADMIN | — | Gateway failure read model |
| `GET /admin/failures/{id}` | redacted error, original event metadata, attempts | ADMIN | not found | Gateway/read model |
| `POST /admin/failures/{id}/retry` | `{reason,targetStage?}` → accepted | ADMIN 10/min | key; not replayable/already active | Owning service |

## 5. Internal API

Chỉ trong Compose network, `X-Internal-Token`, correlation headers bắt buộc:

- `POST /internal/v1/crawl-batches`: Airflow/Gateway tạo batch.
- `GET /internal/v1/crawl-batches/{id}`: Airflow theo dõi batch.
- `GET /internal/v1/source-articles/{id}`: Intelligence/Content/editor detail lấy
  evidence đầy đủ khi event snapshot không đủ.
- `POST /internal/v1/reconciliation/{kind}`: Airflow/manual operator.
- `GET /health/live`, `GET /health/ready` trên từng service.

Không tạo endpoint generic để service đọc table của service khác.

## 6. Mapping frontend hiện có

Frontend hiện là React/Vite, không phải Next.js. Tất cả dữ liệu đang đến từ
`frontend/src/data/mock.ts` hoặc arrays đặt trong admin page. Chưa có API client,
auth persistence, route guards hoặc backend integration.

### Public

| Screen/route hiện có | API | Fields cần |
| --- | --- | --- |
| `HomePage` `/` | `GET /news?pageSize=9`, featured/mixed entities có thể nằm trong response hoặc `GET /search?featured=true` P1 | hero, secondary/latest, source count, status, entity chips |
| `LatestNewsPage` `/tin-moi` | `GET /news?status=&page=` | filters, pagination/load more |
| `PlayersPage` `/cau-thu` | `GET /players?featured=true`, `?hasRecentNews=true` | image placeholder, current club, article count |
| `PlayerDetailPage` | `GET /players/{slug}` | entity + recent news/stories |
| `ClubsPage`, `ClubDetailPage` | club endpoints | league/country, related news/entities |
| `CoachesPage`, `CoachDetailPage` | coach endpoints | current club, related news |
| `SearchPage` `/tim-kiem` | `GET /search?q=&type=` | grouped results, result type, empty/loading/error |
| `ArticleDetailPage` | `GET /news/{slug}` | article body, entities, timeline, sources, related |
| Story detail | `GET /stories/{idOrSlug}` | **Route/component chưa tồn tại**, tạo khi Milestone 3 |
| `NotFoundPage` | không API | giữ hiện có |

### Admin

| Screen hiện có | API | Gap |
| --- | --- | --- |
| `AdminLoginPage` | `/auth/login` | Hiện demo client-side; cần token/session/error thật |
| `AdminDashboard` | planned `GET /admin/dashboard` read model | Metrics hiện hard-coded |
| `AdminSourcesPage` | source/crawl endpoints | Modal chưa validate/submit; thiếu history/detail route |
| Crawl detail | crawl-run endpoints | Component/route chưa tồn tại |
| `AdminArticlesPage` | source-article endpoints | Thiếu detail drawer/page và actions |
| `AdminStoryPage` | story endpoints | Thiếu story detail/editor correction page |
| `AdminDraftPage` | draft endpoints | Cần wire edit/version/approve/reject/publish |
| `AdminPublishedPage` | publications | Unpublish là P1 |
| `AdminErrorsPage` | failures | Wire retry/idempotency |

Mỗi integration phải có:

- typed API models được generate từ OpenAPI hoặc adapter types kiểm soát;
- `loading`, `empty`, `error`, `stale` states;
- abort request khi unmount/search query đổi;
- actionable error cho admin, không hiển thị stack trace;
- mock data chỉ giữ dưới explicit demo/frontend fixture mode, không silently
  fallback khi API production lỗi.

## 7. Contract-first workflow

1. Viết OpenAPI cho một vertical slice.
2. Validate/lint contract.
3. Generate hoặc map TypeScript types.
4. Viết provider/repository contract tests.
5. Implement endpoint.
6. Wire đúng một screen.

Không commit một OpenAPI khổng lồ chưa có consumer. Contract được thêm theo
milestone, nhưng naming/error/pagination ở tài liệu này phải nhất quán.
