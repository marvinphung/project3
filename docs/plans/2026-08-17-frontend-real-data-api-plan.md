# Frontend Real-data và Backend API Plan

## Mục tiêu

Loại bỏ toàn bộ dữ liệu demo khỏi các route đang sử dụng, bảo đảm mọi số liệu,
article, entity, Story, timeline và trạng thái vận hành đều đến từ backend. Thành
phần chưa có API phải hiển thị loading/error/empty state; không được fallback về
fixture. Mỗi button có một trong ba trạng thái rõ ràng: điều hướng thật, gọi API
thật, hoặc disabled kèm lý do.

## Kết quả audit hiện tại

| Khu vực | Hiện trạng | Thiếu contract/backend |
| --- | --- | --- |
| Home | Đã gọi article API nhưng trước đây fallback mock; trending hard-code | Entity aggregation/list API; article pagination |
| Tin mới | Article API có thật; filter và “Xem thêm” chỉ đổi UI/không làm gì | Filter, sort, cursor/total |
| Tìm kiếm | Toàn bộ search result từ mock | Search article/entity API |
| Cầu thủ/CLB/HLV | Route mới tạm suy entity từ publication | Entity list/detail API với article/story count |
| Entity detail | Timeline API có thật; article liên quan đang lọc client-side | Article filter theo entity; entity metadata |
| Article detail | Title/body/timeline thật nhưng entity chips, nguồn, related news còn mock | Article evidence sources và related articles |
| Story detail | Timeline thật; thiếu Story header/metadata | Story detail API |
| Admin dashboard | Toàn bộ metrics, pipeline và activity hard-code | Operational summary/activity API |
| Admin nguồn | List/toggle/crawl có API; thêm/sửa chưa nối | API create/update đã có, cần client/form; trigger hiện chỉ mở batch |
| Admin bài nguồn | Toàn bộ bảng/filter/button mock | Source Article operational API |
| Admin Story | Toàn bộ bảng/filter/button mock | Story operations API |
| Admin bản nháp | Danh sách/nội dung mock; action chỉ chạy nếu fixture tình cờ có UUID | Editorial list/detail/update/regenerate API |
| Admin xuất bản | List public API thật; edit/unpublish chưa hoạt động | Publication admin API |
| Admin lỗi | Toàn bộ bảng và ba action mock | Failure list/detail/retry/ignore API |

## Nguyên tắc API

- Public API chỉ đọc PostgreSQL public projection, không đọc trực tiếp MongoDB.
- Admin operational API có thể đọc projection tổng hợp từ MongoDB/PostgreSQL,
  nhưng không trả raw HTML mặc định; content/evidence dùng endpoint detail.
- List response thống nhất: `items`, `total`, `limit`, `offset`, `next_offset`.
- Filter/sort nằm trong query string để URL có thể bookmark.
- Mutation cần bearer role, idempotency key và optimistic version nếu sửa state.
- Error dùng envelope hiện tại `{error: {code, message, details?}}`.

## Phase 1 — Public frontend không còn mock

### Task 1.1 — Public article query contract

Mở rộng `GET /api/v1/articles` với `q`, `entity_type`, `entity_slug`,
`confirmation`, `sort`, `limit`, `offset`; response thêm pagination metadata.

**Acceptance:** Home/Tin mới/Search/Entity detail dùng một contract; filter và
“Xem thêm” tạo request thật; repository test chứng minh chỉ trả publication.

### Task 1.2 — Public entity directory/detail

- `GET /api/v1/entities?type=PLAYER&q=&limit=&offset=`
- `GET /api/v1/entities/{type}/{slug}`

Detail trả canonical name, aliases hiển thị được, số Story/bài và latest Story
IDs. Không suy danh sách entity từ 100 article ở client.

### Task 1.3 — Story và article evidence

- `GET /api/v1/stories/{story_id}`
- `GET /api/v1/articles/{slug}/sources`
- Related article dùng Task 1.1 với `story_id` hoặc entity filter.

**Acceptance:** Article detail không import mock cho chip, source hoặc related;
Story page có event type, status, confidence và thời gian cập nhật thật.

### Checkpoint 1

- `rg "data/mock" frontend/src` không còn kết quả trong production route.
- Public API contract/repository tests pass; frontend build pass.
- Browser network chỉ gọi `/api/v1/*`; database rỗng hiển thị empty state.

## Phase 2 — Admin observability

### Task 2.1 — Dashboard summary

- `GET /admin/v1/operations/summary`
- `GET /admin/v1/operations/activity?limit=20`

Summary trả counts theo stage (`source_articles`, `intelligence`, `enrichment`,
`stories`, `drafts`, `publications`, `failures`) và timestamp snapshot. Activity
trả bounded event projection, không quét container log trong request.

### Task 2.2 — Source Article inspection

- `GET /admin/v1/source-articles` với source/status/duplicate/date filters.
- `GET /admin/v1/source-articles/{article_version_id}`.

Detail trả crawl metadata, cleaned content, intelligence/enrichment state,
canonical entities, Story link và bounded failure reason.

### Task 2.3 — Failure operations

- `GET /admin/v1/processing-failures`
- `GET /admin/v1/processing-failures/{failure_id}`
- `POST /admin/v1/processing-failures/{failure_id}/retry`
- `POST /admin/v1/processing-failures/{failure_id}/ignore`

Retry phải idempotent và đưa đúng stage về pending; ignore cần reason và audit
actor. Các button “Thử lại/Bỏ qua/Xem chi tiết” gọi đúng endpoint.

### Checkpoint 2

Dashboard, Bài nguồn và Lỗi xử lý hiển thị đúng counts/records đang có trong
Mongo/PostgreSQL; reload không làm phát sinh mutation hoặc duplicate.

## Phase 3 — Story và editorial operations

### Task 3.1 — Admin Story API

- `GET /admin/v1/stories` với status/event/entity/review filters.
- `GET /admin/v1/stories/{story_id}` gồm sources, claims, candidate audit,
  timeline và generated article state.
- Bounded mutation riêng cho merge/reassign/correction, đều optimistic-versioned.

### Task 3.2 — Editorial query/update/regenerate

- `GET /admin/v1/editorial/articles`
- `GET /admin/v1/editorial/articles/{id}`
- `PATCH /admin/v1/editorial/articles/{id}/revisions/{revision_id}`
- `POST /admin/v1/editorial/articles/{id}/regenerate`

Giữ các transition submit/approve/reject/publish hiện có. “Lưu bản nháp” và
“Yêu cầu tạo lại” chỉ enabled khi endpoint tương ứng sẵn sàng.

### Task 3.3 — Publication management

- `GET /admin/v1/publications`
- `POST /admin/v1/publications/{id}/unpublish`

“Chỉnh sửa” tạo revision mới thay vì sửa publication bất biến. Unpublish cần
confirm, reason, idempotency và audit trail.

## Phase 4 — Source management và crawl thật

### Task 4.1 — Hoàn thiện form nguồn

Nối modal thêm/sửa với `POST /admin/v1/sources` và `PATCH /admin/v1/sources/{id}`
đã tồn tại; validate URL/domain/type, version conflict và loading/error state.

### Task 4.2 — Trigger crawl thực sự

Endpoint `/sources/{id}/crawl` hiện chỉ mở `crawl_batch`; cần dispatch job/outbox
để crawler worker nhận batch, hoặc thêm internal job endpoint do Airflow gọi.
UI poll `GET /admin/v1/crawl-batches/{batch_id}` đến terminal state và hiển thị
discovered/fetched/failed.

## Phase 5 — Interaction và browser acceptance

### Task 5.1 — Xử lý control chưa hoạt động

- “Xem thêm” dùng pagination và disabled khi hết trang.
- Filter Tin mới/Story/Bài nguồn cập nhật URL và request.
- Button “Xem” điều hướng tới detail thật.
- Không render button nếu backend chưa hỗ trợ; không để click im lặng.

### Task 5.2 — Browser E2E

Cover public empty/data/error, search, entity → timeline, admin login, source
create/update/crawl-poll, article drill-down, failure retry, editorial publish và
unpublish. Kiểm tra console/network, keyboard/focus và responsive viewport.

## Thứ tự triển khai

`1.1 → 1.2 → 1.3 → 2.1 → 2.2 → 2.3 → 3.1 → 3.2 → 3.3 → 4.1 → 4.2 → 5.x`.
Story/timeline runtime phải chạy trước khi acceptance các phase 1.3 và 3; nếu
không, API đúng vẫn chỉ trả empty state.

## Definition of Done

- Không route production nào import hoặc fallback `data/mock`.
- Không button click im lặng; mọi mutation có progress/success/error.
- OpenAPI, client type và runtime response khớp nhau.
- Focused backend tests, frontend build, Docker smoke và browser E2E đều pass.
- UI hiển thị đúng dữ liệu Mongo/PostgreSQL hiện có và không tự bịa record.
