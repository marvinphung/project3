# Production Readiness & Editorial Automation Implementation Plan

> **Scope update (2026-08-18):** User clarified the immediate target is localhost with real frontend/backend data, not infrastructure production hardening. Use [Local Real-data UI Plan](2026-08-18-local-real-data-ui.md) for the active implementation scope. This document remains a deferred hardening roadmap only.

> **For Codex:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task.

**Goal:** Đưa FootballPulse từ stack local-first/demo thành một bản triển khai production có dữ liệu thật xuyên suốt từ crawl đến publish; không còn dữ liệu mock ở route production; bổ sung cấu hình quản trị để tự duyệt draft đủ điều kiện hoặc chuyển sang duyệt/xuất bản thủ công.

**Architecture:** MongoDB tiếp tục sở hữu source evidence/enrichment; PostgreSQL sở hữu Story, editorial workflow, publication và audit. API Gateway cung cấp read model cho public/admin, tuyệt đối không để frontend đọc DB hoặc gọi worker. Worker giao tiếp bất đồng bộ qua outbox/Kafka, có retry/DLQ và read model vận hành. Cấu hình editorial được lưu bền vững ở PostgreSQL, được kiểm soát bởi RBAC và audit, rồi được worker đọc tại thời điểm quyết định transition.

**Tech Stack:** React/Vite/TypeScript, FastAPI/Pydantic, SQLAlchemy/Alembic/PostgreSQL, PyMongo/MongoDB replica set, Kafka, Redis, Docker Compose hiện hữu; CI, reverse proxy TLS, secret manager và monitoring phù hợp môi trường deploy.

---

## 0. Quy ước và ranh giới phát hành

### 0.1 Target vận hành

1. **Production v1** là một môi trường triển khai thật, có domain/TLS, secret tách khỏi Git, backup/restore đã thử nghiệm, monitoring/alert và quy trình rollback. Không gọi topology một máy là HA multi-region.
2. Nếu yêu cầu SLA/HA cao hơn, tách thành Phase 8: PostgreSQL managed/replica, Mongo replica-set nhiều node, Kafka managed/cluster và object storage. Không tự tuyên bố đạt HA trước khi có hạ tầng đó.
3. `demo`/`test` được phép dùng mock provider; `production` từ chối khởi động nếu bật mock AI, token mặc định, debug mode hay thiếu secret bắt buộc.

### 0.2 Semantics của setting mới

| Cấu hình `auto_approve_drafts` | Luồng draft | Xuất bản |
| --- | --- | --- |
| `false` (mặc định) | Draft tạo ra ở `DRAFT` hoặc `NEEDS_REVIEW`; editor submit/review/approve thủ công | ADMIN publish thủ công, có lý do và audit |
| `true` | Chỉ draft **đạt toàn bộ eligibility guard** được tự chuyển sang `APPROVED`; draft không đạt vẫn vào review queue | Vẫn publish thủ công |

Giả định an toàn này phân biệt rõ *approve* và *publish*, đúng với state machine hiện tại. Nếu muốn tự xuất bản, cần một setting riêng `auto_publish_approved_drafts`, mặc định `false`, với một phê duyệt sản phẩm/bảo mật độc lập; không gộp vào setting auto-approve.

Eligibility guard tối thiểu cho auto-approve: Story/revision hiện hành không stale; enrichment `VALIDATED`; grounding/citation đủ; không có `NEEDS_CONTENT_REVIEW`; model/prompt/input version được lưu; validation EN/VI pass; không bị source/policy blocklist; và không có lỗi pipeline chưa xử lý. Mọi điều kiện không đạt đều fail-closed vào `NEEDS_REVIEW` cùng reason có thể xem được.

## 1. Discovery, contract và migration an toàn

### Task 1.1 — Chốt inventory và baseline có thể tái lập

**Work:**

- Ghi snapshot số lượng theo từng stage, backlog theo status, retry/DLQ, publication và lỗi gần nhất trước migration.
- Kiểm kê tất cả route production còn import/fallback `data/mock`, fixture hard-code, action click im lặng hoặc endpoint chỉ trả một phần dữ liệu.
- Đối chiếu contract DB, API Gateway, worker và frontend; xác định owner/source of truth cho từng số liệu dashboard.
- Hoàn thiện phần `operations/summary` đang dở, kiểm thử và chỉ sau đó dùng nó làm baseline dashboard.

**Acceptance:** Có báo cáo baseline có timestamp; `rg "data/mock" frontend/src` chỉ còn fixture test/demo; mọi gap có issue/phase owner; test API hiện hữu không regress.

### Task 1.2 — Editorial settings và audit schema

**Files/areas:** API Gateway Alembic migration, `content_schema` hoặc schema cấu hình chuyên dụng, editorial repositories/domain, admin API tests.

**Work:**

- Tạo bảng singleton/versioned `editorial_settings`: `id`, `auto_approve_drafts boolean not null default false`, `version`, `updated_at`, `updated_by`.
- Tạo append-only `editorial_audit_log`: action, actor, reason, correlation/idempotency key, aggregate/revision/version, before/after metadata đã redact, timestamp.
- Backfill một row settings an toàn (`false`), unique constraint singleton, permission DB tối thiểu và migration downgrade/restore rehearsal.
- Mở contract `GET /admin/v1/settings/editorial` và `PATCH /admin/v1/settings/editorial`. PATCH chỉ ADMIN, bắt buộc expected version, validate body, emits audit `EDITORIAL_SETTINGS_CHANGED`.

**Acceptance:** Concurrent PATCH trả conflict thay vì ghi đè; mặc định sau deploy luôn manual; audit truy vết được actor, giá trị cũ/mới và correlation ID mà không chứa secret/nội dung thô.

### Task 1.3 — State-machine và idempotency contract

**Work:**

- Viết state transition matrix cho create/edit/submit/approve/reject/publish/unpublish/auto-approve, actor allowed, reason, stale rule và side effect outbox.
- Chuẩn hóa `Idempotency-Key` cho mọi mutation và optimistic version cho revision/settings/source/story mutation.
- Khóa invariant: chỉ current approved revision, Story version hợp lệ và policy pass mới được publish; một publication thành công duy nhất cho revision.

**Acceptance:** Unit/repository tests cover every allowed/denied transition, duplicate request, stale revision và two-actor race.

## 2. Đưa pipeline thật tới review/publish an toàn

### Task 2.1 — Chuẩn hóa trạng thái end-to-end và retry

**Work:**

- Công bố stage/read model chuẩn: `source_articles → enrichment → intelligence/story → editorial revision → publication` cùng counts theo status và timestamp watermark.
- Worker chỉ advance khi event/version hợp lệ; giữ idempotency, retry có exponential backoff, bounded attempts và DLQ/failure record có correlation ID.
- Bổ sung job reconciliation định kỳ để so sánh Mongo/PostgreSQL/outbox, phát hiện event kẹt và replay có kiểm soát.

**Acceptance:** Restart/duplicate delivery không nhân bản Story/draft/publication; một failure có thể nhìn thấy, retry được và không làm mất source evidence.

### Task 2.2 — Xử lý backlog `NEEDS_CONTENT_REVIEW` đúng nghiệp vụ

**Work:**

- Tạo review queue có evidence summary, quality failure reason, source, model/version và action `validate`, `reject`, `retry` có RBAC/audit.
- Không dùng auto-approve để bypass quality gate. Chỉ content được reviewer validate mới có thể tạo Story/draft.
- Thêm bulk action giới hạn, preview selection, idempotency và rate limit để triage backlog lớn an toàn.

**Acceptance:** Bài chưa đạt quality gate không tạo draft/publish; reviewer xử lý được một batch có audit; dashboard giải thích rõ vì sao số source lớn nhưng số draft thấp.

### Task 2.3 — Draft generation và auto-approve policy

**Work:**

- Tại điểm worker tạo current revision, đọc `editorial_settings` theo request/job; evaluate eligibility guard thuần hàm và lưu từng kết quả rule.
- Khi setting bật và pass, thực hiện transition transactionally sang `APPROVED`, ghi actor hệ thống (`editorial-policy`), policy/model/input versions, audit/outbox.
- Khi setting tắt hoặc fail, lưu `DRAFT`/`NEEDS_REVIEW` theo workflow, reason hiển thị cho editor; không retry vô hạn chỉ vì fail policy.
- Có endpoint/detail admin để xem approval provenance và lọc `auto_approved`, `manual_approved`, `needs_review`.

**Acceptance:** Test matrix bật/tắt setting, stale draft, invalid citation, quality-review pending, race settings change và replay event; không tồn tại trường hợp auto-publish.

### Task 2.4 — Editorial và publication command hoàn chỉnh

**Work:**

- Hoàn thiện list/detail/update/regenerate revision server-side pagination/filter; edit tạo revision mới và invalidates approval cũ.
- Hoàn thiện approve/reject/publish/unpublish; publish/unpublish yêu cầu reason/confirmation, idempotency và immutable public snapshot.
- Publication outbox có delivery status, retry/DLQ và reconciliation để public projection không drift.

**Acceptance:** Editor không thể approve/publish quá quyền; admin có thể publish/unpublish có audit; public API chỉ thấy publication active và never reads Mongo directly.

## 3. Thay toàn bộ giao diện admin bằng dữ liệu thật

### Task 3.1 — Dashboard vận hành và activity feed

**Work:**

- Nối `AdminDashboard` vào `GET /admin/v1/operations/summary` và `activity`; trả source/enrichment/story/revision/publication/failure counts có watermark và definition tooltip.
- Activity là event projection bền vững, không scrape container logs trong request; implement loading/error/empty/stale states.
- Bỏ toàn bộ metric/pipeline/recent activity fixture.

**Acceptance:** Dashboard phản ánh database khi reload, biết trạng thái snapshot và không tạo mutation khi xem.

### Task 3.2 — Bài nguồn, nguồn crawl, Story và lỗi xử lý

**Work:**

- Hoàn thiện source article list/detail server-side filters: source/status/date/q/duplicate; raw HTML chỉ detail có quyền phù hợp, default redacted.
- Nối create/update/toggle/crawl source form thật; crawl dispatch qua outbox/job, poll batch thật và hiện số discovered/fetched/failed.
- Thêm admin Story list/detail (claims, evidence references, candidates, revision state) và failure list/detail/retry/ignore APIs có audit.
- Bỏ fallback source/stories/errors fixtures; action không hỗ trợ phải disabled kèm lý do, không click im lặng.

**Acceptance:** 1,655 source records hiện đúng pagination thay vì 4 fixture; failure/retry/status từ DB; mọi mutation có progress, result, error state.

### Task 3.3 — Draft, publication và settings UX

**Work:**

- Draft page dùng pagination/filter trạng thái thật, revision detail, approval provenance, compare/diff and evidence links.
- Published page dùng admin publications API (không giả editor/views); unpublish flow confirmation/reason và history.
- Thêm Settings > Editorial: switch `Tự duyệt draft đủ điều kiện`, warning rằng **không tự publish**, version conflict UI, last changed by/at, audit history và quyền ADMIN-only.

**Acceptance:** Khi toggle off, draft mới chờ editor; khi toggle on, chỉ eligible draft nhận `APPROVED` do policy; UI không thể che giấu/manual override audit.

## 4. Public UI, data contract và hiệu năng

### Task 4.1 — Xóa mock/fallback khỏi public routes

**Work:**

- Hoàn thiện article/entity/story/source/related/search API with query pagination/filter/sort and explicit empty responses.
- Refactor Home, News, Search, entity detail, article detail, Story detail để chỉ dùng typed API client; URL query là source of truth cho filter/pagination.
- Cấm fixture fallback trong production bundle; test/demo fixture được cô lập rõ.

**Acceptance:** DB empty hiển thị empty state trung thực; UI data/error/loading accessible; network chỉ gọi supported API routes.

### Task 4.2 — API quality, security và performance

**Work:**

- Publish OpenAPI/typed client contract, error envelope thống nhất, cursor/offset limits, input validation and query indexes cho list lớn.
- Enforce authn/authz server-side, rate limits cho admin mutations/retry, CSRF strategy nếu cookie auth, token rotation/expiry nếu bearer, security headers/CORS/CSP.
- Implement bounded projections and cache only safe public read models; đo p95 dashboard/list/detail, tránh N+1/cross-DB full scans on request.

**Acceptance:** Security tests reject privilege escalation/invalid input; load test đạt target đã chốt; no raw content/secrets in API/logs.

## 5. Hạ tầng production, secret và dữ liệu bền vững

### Task 5.1 — Build, runtime và configuration hardening

**Work:**

- Tách Compose local/demo với production manifest/image immutable digest; rootless/non-root runtime, read-only filesystem where possible, resource limits, liveness/readiness/startup probes.
- Validate all production env at startup: DB/Kafka/Redis/Mongo URL, admin bootstrap/identity, CORS/origin, provider, encryption/TLS. Ban default credentials/mock/debug.
- Chuyển secret khỏi `.env`/image/log sang secret manager hoặc deployment secret store; quy trình rotation và least-privilege service credentials.

**Acceptance:** Production preflight fail-closed; image vulnerability/dependency scan không có blocker được chấp nhận; config/secret không xuất hiện trong git, client bundle hay log.

### Task 5.2 — Database, backup và disaster recovery

**Work:**

- Bật authentication/TLS/network policy cho Mongo/Postgres/Kafka/Redis; define encryption at rest theo hạ tầng chọn.
- Lập backup encrypted/scheduled/retention, point-in-time strategy nếu managed DB; test restore vào môi trường cách ly, verify referential/state integrity.
- Document retention/deletion cho raw article/evidence/log/audit; migrate index/schema theo expand-migrate-contract, có rollback compatibility.

**Acceptance:** Restore drill đạt RPO/RTO đã chốt; backup không chứa secret plaintext; migration rollback/release previous image được rehearsal.

### Task 5.3 — Kaggle/AI production governance

**Work:**

- Verify provider privacy/quota/timeout/data classification trước khi gửi data thật; pin model/prompt/kernel/dataset versions and checksum.
- Set batch limits/backpressure/cost quota; provider outage giữ input và emits actionable failure instead of bypassing validation.
- Real provider smoke chạy với một source được phép, có approval trước khi tiêu quota/data.

**Acceptance:** Kaggle outage/retry/partial/corrupt output tests pass; no raw HTML or credential leaves boundary; actual run is reported separately from mock test.

## 6. Observability, operations và support

### Task 6.1 — Logs, metrics, traces và alerts

**Work:**

- Structured logs carry correlation ID, article/story/revision/batch IDs, event/action/status and redact PII/secrets/raw body.
- Metrics: queue lag, event age, worker throughput/failure/retry/DLQ, status backlog, auto-approval decision counts, publish latency, API error/latency, DB connection pool.
- Distributed trace across gateway/outbox/worker where feasible; dashboards plus alerts for pipeline stall, DLQ growth, failed backup, auth errors, provider quota and low disk.

**Acceptance:** On-call can trace one source article to publication; a seeded worker failure produces alert, dashboard record and documented recovery.

### Task 6.2 — Runbooks and operating controls

**Work:**

- Write runbooks for deploy, rollback, migration failure, queue replay, provider outage, invalid publication, backup restore, credential rotation and auto-approve emergency disable.
- Add health/readiness endpoint semantics and deployment smoke checks; define incident severity, owner, escalation and communication template.
- Add kill switch for new draft generation and auto-approve evaluation; disabling takes effect for subsequent transitions immediately and is audited.

**Acceptance:** A second operator can use runbook to disable auto-approval, replay one safe event and roll back one release without source loss.

## 7. Quality gates, rollout và launch

### Task 7.1 — Test pyramid and CI/CD

**Work:**

- Unit/repository/contract tests for state machine, setting, audit, API filters and failure commands; integration tests with Mongo replica set/Postgres/Kafka; frontend component and browser E2E tests.
- CI gates: formatting/lint/typecheck, test suites, migration validation, build, SBOM/dependency/vulnerability scan, secret scan, OpenAPI/client drift and Compose render.
- Versioned artifacts, provenance, staging deploy with smoke, production deploy approval and automatic/operational rollback criteria.

**Acceptance:** Every merge has reproducible evidence; no deployment may skip migration/test/security gate without recorded exception.

### Task 7.2 — Staged data and feature rollout

**Work:**

1. Deploy schema/API/read-only admin UI with `auto_approve_drafts=false`.
2. Verify real source/backlog/dashboard/stories/drafts/publications in staging, then a small production canary source set.
3. Run manual editorial acceptance on eligible and ineligible content; resolve backlog quality review separately.
4. Enable `auto_approve_drafts=true` only in staging first, then limited production cohort/source class, monitor approval/failure/audit metrics.
5. Keep publishing manual. Expand only after explicit product/editorial sign-off.

**Rollback:** Disable setting immediately; stop draft generator if needed; retain already approved revisions for manual review; never delete source/evidence/audit; roll back app only after checking schema compatibility.

**Acceptance:** Canary has no unexplainable state transitions, no unauthorized publish, SLO/error budget targets met during agreed observation window, and owner signs launch checklist.

## 8. Final Definition of Done

- Every production route uses backend data; no mock/fallback or inactive silent button remains.
- Pipeline has a visible, retryable path from source to editorial queue/publication, and reports why items stop at each gate.
- `auto_approve_drafts` is persisted, default-off, ADMIN-controlled, optimistic-versioned, fail-closed, audited and independently kill-switchable; it never auto-publishes.
- Auth/RBAC, idempotency, audit, input validation, TLS/secrets, backups/restore, monitoring/alerts and runbooks are verified rather than documented only.
- CI/CD, staging/canary, smoke/E2E/load/security/recovery tests pass with evidence; production deployment and rollback are rehearsed.
- The final handoff records real provider run evidence separately from deterministic mock/offline tests, plus known non-HA limits if Phase 8 is not funded.

## Execution order and release gates

`1.1 → 1.2 → 1.3 → 2.1 → 2.2 → 2.3 → 2.4 → 3.x → 4.x → 5.x → 6.x → 7.1 → 7.2`.

Do not enable the setting in production before Phase 2 tests, the audit trail, dashboard/queue visibility, emergency disable and a staging canary all pass. Do not call the system HA production until Phase 8 infrastructure has been implemented and exercised.
