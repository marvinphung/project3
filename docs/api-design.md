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
  "event_id": "stable-unique-id",
  "event_type": "article.enriched",
  "schema_version": 1,
  "occurred_at": "UTC timestamp",
  "producer": "ai-content-service",
  "correlation_id": "batch-trace-id",
  "causation_id": "previous-event-id",
  "aggregate_id": "article-version-id",
  "payload": {}
}
```

Topic vật lý theo `<domain>.<event>.v1`; breaking change tạo version mới. Event
không chứa raw HTML hoặc secret.

## 7. Event catalog tối thiểu

| Topic | Producer → Consumer | Payload cốt lõi |
| --- | --- | --- |
| `article.discovered.v1` | Crawler → Article | source/batch IDs, URL, bounded fetch snapshot |
| `article.cleaned.v1` | Article → Intelligence | article version ID, hash, cleaned snapshot, duplicate result |
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
