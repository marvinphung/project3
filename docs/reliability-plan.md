# Kế hoạch reliability và data consistency

## 1. Producer policy

Mọi business producer:

- `acks=all`.
- `enable.idempotence=true` khi client hỗ trợ.
- Bounded retries, delivery timeout và request timeout.
- Stable `event_id`; stable key theo catalog.
- Gọi `poll()`/`flush()` để delivery callback thực sự chạy.
- Chỉ coi queued khi delivery callback xác nhận Kafka đã nhận.
- Crawler chỉ tăng `queued_count` và đánh dấu article queued sau confirmation.
- Producer error được phân loại `RETRYABLE|PERMANENT|OPERATOR`.

Idempotent Kafka producer chỉ giảm duplicate do producer retry; nó không thay
thế business idempotency downstream và không tạo exactly-once toàn hệ thống.

## 2. Consumer policy

- `enable.auto.commit=false`.
- Poll một bounded batch; pause partition hoặc giới hạn inflight.
- Validate schema.
- Trong transaction: kiểm `processed_events`, apply business mutation, insert
  processed record, insert outbox.
- Commit DB.
- Manual synchronous offset commit cho message/batch đã hoàn thành.
- Nếu crash trước offset commit, Kafka redeliver và `processed_events` biến nó
  thành no-op an toàn.
- Không commit nếu durable processing chưa xong.
- Graceful shutdown: stop polling, finish/cancel bounded work theo timeout,
  không commit unfinished messages, close consumer/DB clients.

## 3. Transactional outbox theo service

### Article Service

MongoDB transaction ghi:

```text
source_articles
+ article_identities
+ processed_events
+ outbox_events
```

Outbox publisher chạy cùng service như background process riêng. Mongo local
dùng single-node replica set. Reconciliation:

- `UNIQUE` article không có `article.unique` outbox;
- outbox `PUBLISHING` lease expired;
- `PUBLISHED` không có delivery metadata.

### Intelligence Service

Một PostgreSQL transaction ghi story/entity/claim/timeline/version,
`processed_events` và `outbox_events`. Đây là nơi outbox quan trọng nhất vì
generation phải theo đúng `story_version`.

### AI Content Service

Một PostgreSQL transaction ghi generation result/attempt và
`content.draft.created` outbox. Provider call không nằm trong DB transaction:
job chuyển `RUNNING`, gọi provider, sau đó transaction lưu result. Worker restart
claim lại lease expired job.

### Content Service

Draft/revision/editorial/publication và outbox cùng PostgreSQL transaction.
Publish condition:

```text
draft.status = APPROVED
AND draft.current_revision_id = requested_revision_id
AND draft.version = expected_version
AND no successful publication exists
```

## 4. Retry, backoff và DLQ

Error classes:

- Transient: network timeout, Kafka broker unavailable, PG/Mongo transient,
  provider 429/selected 5xx → quick retry + delayed retry.
- Permanent: schema invalid, unsupported URL, malformed provider output sau
  correction attempts, invalid state transition → DLQ/NEEDS_REVIEW.
- Operator/editor: alias ambiguity, story score gray zone, conflicting claims,
  exhausted source/provider attempts.

Backoff planned:

```text
delay = random(0, min(cap, base * 2^attempt))
```

`Retry-After` hợp lệ được ưu tiên nhưng clamp vào max. Không retry vô hạn. DLQ
record gồm original event, topic/partition/offset, attempts, timestamps,
classification, redacted error, replay policy và correlation chain.

Admin retry:

- không sửa original DLQ;
- tạo event replay mới với event ID mới, `causation_id` trỏ failure/original;
- business idempotency key giữ nguyên hoặc có generation suffix theo command;
- audit actor/reason.

## 5. Reconciliation

Scheduled/manual service commands, được Airflow gọi ở workflow level:

- Article: missing/leased outbox, stuck processing.
- Intelligence: missing story versions/outbox, source event processed nhưng
  chưa có story link.
- AI: expired RUNNING lease, successful job thiếu draft event.
- Content: published record thiếu public read model/event.
- Kafka: lag/DLQ thresholds.

Reconciliation không thay Kafka polling cho work bình thường.

## 6. Failure matrix

| Failure | Hành vi | Recovery evidence |
| --- | --- | --- |
| Kafka unavailable khi crawler produce | Crawler attempt retry; không đánh dấu queued | queued count không tăng; delivery error metric |
| Mongo insert xong, service crash | Transaction/outbox bảo đảm event tồn tại; offset chưa commit → redelivery | processed event no-op; outbox publisher phát |
| Consumer crash trước offset commit | Redelivery | business unique constraints không tạo bản ghi lặp |
| Outbox publish xong, crash trước mark | Event phát lại | downstream event ID idempotency |
| Redis unavailable | Public GET fallback; sensitive/admin/AI/crawler distributed actions hạn chế hoặc pause | degraded readiness + metrics |
| Mongo unavailable | Article consumer không commit; retry/DLQ sau budget | Kafka giữ event theo retention |
| PostgreSQL unavailable | Intelligence/AI/Content không commit; retry | offset chưa commit; alert lag |
| Provider 429/5xx/timeout | bounded retry + limiter pause | attempt/usage record; failure event |
| Invalid AI JSON/claim | correction attempt rồi `INVALID/NEEDS_REVIEW` | không tạo publishable draft |
| Concurrent story create | unique fingerprint/lock; loser re-read và attach | một active story, links đầy đủ |
| Concurrent publish | conditional state/version + unique publication | đúng một successful publication |
| Poison message | bounded attempts → DLQ; partition tiếp tục | failure visible/replayable |

## 7. Observability và recovery objectives

Không đặt SLO production giả trong đồ án. Demo acceptance:

- mọi event tra từ request/correlation/event ID qua structured logs;
- lag, retry, DLQ, outbox pending và stuck job có operational counters/read
  models phục vụ admin dashboard;
- liveness chỉ phản ánh process; readiness phản ánh dependency cần thiết;
- restart worker giữa message không mất durable work;
- runbook mô tả inspect/retry/reconcile.

Toàn bộ hệ thống chỉ nhắm localhost. Không dùng Prometheus hoặc Grafana; health
endpoints, JSON logs, Kafka consumer-group inspection, Kafka UI tùy chọn và
admin failure/operations screens là đủ cho phạm vi đồ án.
