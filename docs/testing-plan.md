# Kế hoạch kiểm thử FootballPulse

Các command dưới đây là **planned**, chưa có configuration và chưa được chạy.
Khi implementation tạo command, phải chạy thành công rồi mới cập nhật README và
`AGENTS.md`.

## 1. Test pyramid và tooling đề xuất

| Layer | Tool đề xuất | Phạm vi |
| --- | --- | --- |
| Python unit | `pytest`, `pytest-asyncio`, `time-machine` | Pure domain rules, async adapters, deterministic time |
| Property tests | `hypothesis` có chọn lọc | URL normalization, idempotency/state transition invariants |
| HTTP/API | FastAPI `TestClient`/HTTPX ASGI transport | Middleware, auth, validation, error contract |
| Mongo/Postgres/Redis/Kafka integration | `pytest` + Docker Compose test profile hoặc Testcontainers | Repository, transaction, outbox, consumer semantics |
| Contract | `jsonschema`, OpenAPI validator, Pydantic fixture roundtrip | Event/API/provider compatibility |
| Frontend | Vitest + React Testing Library (planned, chưa có) | API adapters, loading/error, forms |
| Browser E2E | Playwright (planned) | Review/publish/public path |
| Load | Locust cho HTTP; purpose-built Python runner cho crawler/Kafka | Bounded concurrency, lag, rate limit |
| Quality | Ruff + mypy | Format/lint/type checking |

Không mock database/Kafka trong integration test. Unit test repository interface
có thể dùng fake nhỏ, nhưng failure/restart/idempotency phải dùng real
containers.

## 2. Unit tests

### Crawler

- URL scheme/domain/DNS/private-IP/redirect validation.
- Global/per-domain semaphore không vượt limit.
- Token-bucket/sliding-window rate limit.
- Timeout/response-size/redirect limits.
- Retry classification: 429, 408, selected 5xx, DNS, TLS, malformed content.
- `Retry-After` seconds/date parsing và clamp.
- Full-jitter backoff với seeded RNG.
- Cancellation/graceful shutdown không đánh dấu queued.

### Article

- URL canonicalization: host/scheme case, tracking params, fragment, slash,
  canonical link.
- Unicode/title/content whitespace normalization.
- Stable SHA-256 normalized content hash.
- SimHash/title/Jaccard similarity golden cases.
- URL/exact/near duplicate decision.
- Duplicate evidence không bị xóa và không tăng source diversity sai.

### Intelligence

- Keyword khác entity mention.
- Longest alias match, Unicode/diacritics/case, overlapping aliases.
- `Man Utd`, `Manchester United`, `MUFC` → một entity.
- Entity type classification và unresolved ambiguity.
- Event category golden fixtures.
- Claim fingerprint/source support/uncertainty preservation.
- Candidate retrieval filters, score components, threshold boundaries.
- Story fingerprint, confirmation transitions, version increment.
- Merge/reassign invariants.

### AI/Content

- Provider request/response schema.
- Unknown claim/source IDs bị reject.
- Confirmation strengthening bị reject.
- Deterministic mock output snapshot.
- Provider retry classifications/usage accounting.
- Editorial transition matrix.
- Edit after approve invalidates approval.
- Idempotent publish và stale revision conflict.

## 3. Integration tests

### Kafka

- Producer delivery callback với `acks=all` planned config.
- Schema/key/header đúng contract.
- Auto commit tắt; offset chỉ commit sau durable write.
- Crash sau DB commit trước offset commit → redelivery no-op.
- Retry topic/DLQ chứa original metadata.
- Graceful close không commit inflight.

### MongoDB

- Index creation/uniqueness.
- Transaction evidence + identity + processed event + outbox.
- Hai concurrent exact duplicates tạo hai evidence nhưng một primary identity.
- Outbox lease/reclaim.
- Replica-set startup/restart.

### PostgreSQL

- Alembic upgrade từ empty DB cho từng schema.
- FK/unique/check constraints.
- Processed event + state + outbox atomic.
- Hai workers create cùng fingerprint → một active story.
- Hai workers update story → không lost timeline/claim.
- Hai publish requests → một publication.
- Full-text/trigram search theo canonical và alias.

### Redis

- Public/admin/crawler/provider limiter correctness.
- Expiration/window boundary.
- Multi-worker contention.
- Outage behavior đúng fail-open/fail-closed policy.
- Explicit client/pool close.

## 4. Contract tests

- Mọi JSON Schema có valid example và invalid fixtures.
- Producer fixture validate bằng schema mà consumer dùng.
- Backward-compatible optional addition không phá v1.
- OpenAPI path/request/response/error/pagination được validate.
- Frontend generated/mapped types compile với OpenAPI fixture.
- `MockProvider`, `OpenAIProvider`, `OpenRouterProvider` chạy chung provider
  contract suite; real provider tests opt-in, không ở CI/offline.

## 5. End-to-end scenarios

### E2E happy path

```text
manual/Airflow batch
→ Mock RSS + HTML
→ article.discovered
→ Mongo evidence
→ article.unique
→ canonical entities/story/claims/timeline
→ generation request
→ Mock AI draft
→ editor approve/publish
→ public API
→ React article detail/search/entity page
```

Assertions:

- IDs/correlation trace xuyên pipeline;
- source count và references chính xác;
- story có nhiều source;
- draft citations chỉ dùng supported claims;
- public article là generated content, không overwrite evidence.

### E2E evolving story

Chạy scenario theo stages: rumour → reported → rejected bid → coach comment →
official. Kiểm một story được update, version/timeline tăng, confirmation không
nhảy sai, generation request chỉ khi change meaningful.

### E2E unrelated content

Injury và match article tạo story riêng, không nhập transfer story dù cùng club.

## 6. Failure tests

| Case | Injection | Assertion |
| --- | --- | --- |
| 429 | Mock source/provider trả `Retry-After` | đúng delay/attempt, không vượt rate |
| 500 | N lần rồi success | bounded retry, một business record |
| Timeout/slow | delayed response | cancel, retry, no false queued |
| Consumer redelivery | kill trước commit | processed event no duplicate |
| Article saved/event fail | stop Kafka/outbox publisher | outbox phát sau recovery |
| Invalid AI | malformed/unsupported claim mode | `INVALID`, không publish |
| Story race | 2 consumers/transactions | một active story, no lost link |
| Publish race | 2 commands same key/different keys | một publication |
| Worker restart | stop/restart each worker at checkpoint | durable unfinished work resumes |
| Redis down | stop Redis | policy fail-open/closed đúng, data intact |
| Mongo down | stop Mongo | Article không commit, recovers/retries |
| Postgres down | stop PG | downstream không commit; lag visible |
| Poison message | invalid schema | DLQ, next partition messages progress |

## 7. Load/concurrency tests

Không đặt target giả trước khi baseline. Mỗi run ghi:

- machine CPU/RAM/OS và Docker resource limits;
- service replica/worker/concurrency counts;
- Kafka broker/partitions;
- payload/body sizes và number of sources/articles;
- duration và warm-up;
- throughput, p50/p95/p99 latency, errors;
- Kafka lag peak/end;
- Mongo/PG write rate;
- story conflict/retry counts;
- final invariants (unique stories/publications, evidence count).

Experiments:

1. Crawler concurrency 1/4/8/16 với hai domains và configured limits.
2. Article consumer throughput với exact duplicate ratios 0/25/50%.
3. Intelligence backlog với same-story contention 0/50/90%.
4. AI mock limiter/concurrency; real provider load **không chạy mặc định**.
5. Public news/search rate limiter và query latency.

Kết quả lưu `docs/results/YYYY-MM-DD-<scenario>.md`; không invent số liệu.

## 8. CI stages planned

1. Contract/format/lint/type checks.
2. Python unit tests và frontend build/test.
3. Integration profile Mongo/Postgres/Redis/Kafka.
4. E2E mock happy path.
5. Failure/load chạy manual hoặc nightly vì tốn thời gian.

CI là P1 sau Milestone 2; localhost commands phải ổn trước. Không dùng
Prometheus/Grafana trong test hay runtime.

## 9. Planned commands

Tên command mục tiêu:

```bash
uv run pytest tests/unit
uv run pytest tests/contract
uv run pytest tests/integration
uv run ruff check .
uv run ruff format --check .
uv run mypy services packages
pnpm --dir frontend build
docker compose --profile test up --build --abort-on-container-exit
```

Đây chưa phải command đã xác minh. Task implementation phải tạo config, chạy
và cập nhật tài liệu từng command.
