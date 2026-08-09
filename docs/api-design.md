# Thiết kế API và event

## 1. Mục tiêu

Đây là capability design, chưa phải OpenAPI đã triển khai. HTTP phục vụ query và
admin command cần phản hồi; Kafka vận chuyển business event giữa owner. Gateway
không chứa crawl, Story, AI hay publication logic.

## 2. Quy ước HTTP

- Public/admin prefix `/api/v1`; internal capability `/internal/v1`.
- ID ổn định, timestamp UTC; response timeline đổi sang timezone yêu cầu.
- List endpoint dùng cursor pagination, stable ordering và filter rõ ràng.
- Mutation quan trọng nhận `Idempotency-Key` và `expected_version`.
- Error envelope: `code`, `message`, `request_id`, `details` đã sanitize.
- UI mặc định `vi`; English fields không expose công khai trừ admin/debug scope.

## 3. Public timeline API

| Method/path | Mục đích |
| --- | --- |
| `GET /api/v1/players/{slug}/timeline` | Timeline các Story liên quan cầu thủ |
| `GET /api/v1/clubs/{slug}/timeline` | Timeline các Story liên quan CLB |
| `GET /api/v1/coaches/{slug}/timeline` | Timeline các Story liên quan HLV |
| `GET /api/v1/competitions/{slug}/timeline` | Timeline theo giải đấu |
| `GET /api/v1/stories/{id}` | Story public projection và timeline |
| `GET /api/v1/articles` | Danh sách Generated Articles đã publish |
| `GET /api/v1/articles/{slug}` | Immutable publication snapshot |

Timeline hỗ trợ `from`, `to`, `event_type` và cursor. Content Service query
PostgreSQL read model; request UI không query MongoDB, chạy embedding hoặc gọi
AI.

Response mẫu:

```json
{
  "entity": {"id": "player-vinicius-junior", "name": "Vinícius Júnior"},
  "timeline": [
    {
      "timestamp": "2026-08-01T12:00:00+07:00",
      "summary": "Arsenal đã gửi đề nghị trị giá 180 triệu euro.",
      "confirmation": "MULTI_SOURCE",
      "story_id": "story-789",
      "sources": [{"name": "BBC Sport", "url": "https://..."}]
    }
  ],
  "next_cursor": null
}
```

Không trả entry cho cửa sổ không có material change.

## 4. Admin capabilities

| Capability | Quyền |
| --- | --- |
| CRUD/toggle RSS source, crawl policy, reliability metadata | Admin |
| Trigger crawl batch, retry/replay/reprocess | Admin |
| Xem batch → source → article → enrichment → Story → timeline | Editor/Admin |
| Xem raw evidence và AI validation reasons | Editor/Admin theo scope |
| Resolve entity alias, reassign/merge Story | Admin |
| Review timeline bị flag | Editor/Admin |
| Edit/approve/reject long-form draft | Editor/Admin |
| Publish approved current revision | Admin |

Admin Dashboard đọc operational read models theo `batch_id`, không parse logs.
State command gửi `expected_version`; conflict yêu cầu UI tải lại state.

## 5. Internal capabilities

- Tạo/đọc/đóng crawl batch.
- Lấy enabled sources đến hạn.
- Tạo AI batch manifest, cập nhật Kaggle job status và import partial results.
- Yêu cầu reprocess theo article/story/model/prompt version.
- Lấy bounded evidence detail theo owner API khi event snapshot không đủ.

Internal API dùng configured service identity/token trong local Compose network.
Nó không phải arbitrary crawl proxy và không cho query storage chéo ownership.

## 6. Event envelope

```json
{
  "event_id": "018f8b45-b634-7c81-a47d-9a7c2f3c2101",
  "event_type": "article.discovered",
  "event_version": 1,
  "occurred_at": "2026-08-01T00:02:00Z",
  "producer": "crawler-service",
  "correlation_id": "018f8b45-b634-7c81-a47d-9a7c2f3c2102",
  "causation_id": null,
  "aggregate_type": "source_article",
  "aggregate_id": "018f8b45-b634-7c81-a47d-9a7c2f3c2103",
  "idempotency_key": "rss:bbc-sport:item-vinicius-20260801",
  "payload": {}
}
```

`event_type` không chứa version; topic vật lý theo `<event_type>.v<event_version>`.
ID dùng UUID, timestamp phải có timezone và producer/aggregate dùng stable slug.
Root event có `causation_id = null`; event kế tiếp trỏ về event trực tiếp tạo ra
nó. `correlation_id` giữ nguyên xuyên suốt một crawl batch.

Runtime model Pydantic là nguồn sự thật; JSON Schema Draft 2020-12 được commit ở
`contracts/events/` và parity test ngăn schema trôi khỏi model. V1 là immutable:
đổi field, constraint hoặc semantics đều tạo model/schema/topic version mới.
Consumer validate tại boundary và từ chối unknown field. Event không chứa raw
HTML, cleaned body, embedding, secret hoặc AI prompt lớn.

### 6.1 `article.discovered.v1`

Payload chỉ mang RSS/fetch metadata: `source_id`, `batch_id`, canonical URL,
bounded RSS title/GUID, publish/fetch timestamp, HTTP metadata và
`fetch_artifact_id`. `fetch_artifact_id` là opaque handoff reference; cơ chế lưu
artifact được khóa trước WP crawl, không được biến field này thành local path
hoặc nhét HTML vào Kafka.

### 6.2 `article.cleaned.v1`

Payload mang source/article/version IDs, canonical URL, bounded title, SHA-256,
English language marker, cleaned timestamp, Mongo document reference và duplicate
result. Cleaned content được đọc từ MongoDB qua owner boundary, không nằm trong
event. `duplicate_of_article_version_id` bắt buộc với `URL`, `EXACT`, `NEAR` và
phải `null` với `NONE`.

## 7. Event catalog tối thiểu

| Topic | Producer → Consumer | Payload cốt lõi |
| --- | --- | --- |
| `article.discovered.v1` | Crawler → Article | source/batch IDs, URL, RSS/fetch metadata, opaque artifact ID |
| `article.cleaned.v1` | Article → Intelligence | article/version IDs, hash, Mongo reference, duplicate result |
| `article.duplicate.v1` | Article → Ops projection | duplicate IDs, type, score/reason |
| `article.enrichment.requested.v1` | Intelligence → AI Content | article ID/hash, canonical entities, embedding reference |
| `article.enriched.v1` | AI Content → Intelligence | validated English summary/claims and model metadata |
| `story.updated.v1` | Intelligence → Content | Story/version, material changes, claims/source snapshots |
| `timeline.created.v1` | Content → Public projection | window, EN/VI summary, confirmation, sources |
| `content.generation.requested.v1` | Intelligence/Admin → AI Content | Story/version/claims/prompt version |
| `content.draft.created.v1` | AI Content → Content | validated bilingual draft and citations |
| `publication.published.v1` | Content → Public projection | immutable publication snapshot identity |

## 8. Retry, DLQ và idempotency

Mỗi retryable input có tối đa `<base>.retry.v1` và `<base>.dlq.v1`. Retry giữ
original event, attempt, `next_attempt_at` và redacted error. Offset chỉ commit
sau durable state. Event ID chống redelivery; stable business keys bảo vệ
article version, StorySource, claim, `(story_id, window_start)`, generation và
publication khỏi lặp.
