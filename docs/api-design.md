# Thiết kế API và event

## 1. Mục tiêu

Tài liệu này định nghĩa **capability và ranh giới**, chưa phải OpenAPI đã triển
khai. HTTP dùng cho public query/admin command cần phản hồi; event dùng cho
pipeline giữa các owner. Gateway không chứa business logic và service không
truy cập database của nhau.

## 2. Quy ước HTTP

- Prefix version: `/api/v1`; internal capability: `/internal/v1`.
- ID và timestamp ổn định; timestamp biểu diễn UTC.
- List endpoint có pagination, filter và stable ordering.
- Mutation quan trọng nhận idempotency key và expected version khi phù hợp.
- Error envelope tối thiểu: `code`, `message`, `request_id`, `details` an toàn.
- Mọi request có request/correlation ID; internal call truyền tiếp identity đó.

## 3. Public capabilities

| Method/path logic | Mục đích |
| --- | --- |
| `GET /api/v1/articles` | Danh sách publication, filter category/entity |
| `GET /api/v1/articles/{slug}` | Chi tiết snapshot đã publish và references |
| `GET /api/v1/stories/{id}` | Story summary/timeline công khai nếu được expose |
| `GET /api/v1/entities/{id}` | Entity cùng các publication liên quan |

Public response chỉ dùng public projection, không lộ provider raw response,
processing error nội bộ hay full scraped content.

## 4. Admin/editorial capabilities

| Capability | Quyền |
| --- | --- |
| Xem sources, crawl runs, Source Articles và failures | Editor/Admin tùy dữ liệu |
| Trigger crawl/retry/replay | Admin |
| Xem Story, claims, source support | Editor, Admin |
| Sửa entity, reassign/merge Story | Admin |
| Xem/sửa draft, tạo revision | Editor, Admin |
| Submit review, approve, reject | Editor, Admin |
| Publish approved current revision | Admin |

Command sửa state phải gửi `expected_version`; conflict trả về lỗi rõ để UI tải
lại state mới. Approve/reject/publish bắt buộc có actor và có thể có reason.

## 5. Internal capabilities

Các capability như tạo crawl batch, đọc batch status, yêu cầu reprocess hoặc lấy
evidence detail chỉ dành cho service/orchestrator đã xác thực. Chúng không được
expose như arbitrary crawl proxy và không cho phép service query trực tiếp
storage của owner khác.

## 6. Event envelope

Mỗi event quan trọng gồm:

```json
{
  "event_id": "stable-unique-id",
  "event_type": "article.discovered",
  "schema_version": 1,
  "occurred_at": "UTC timestamp",
  "producer": "crawler-service",
  "correlation_id": "trace-id",
  "causation_id": "previous-event-id-or-null",
  "aggregate_id": "domain-id",
  "payload": {}
}
```

Topic vật lý theo `<domain>.<event>.v1`; thay đổi breaking tạo version mới.
Payload phải bounded, validate được và chỉ mang dữ liệu consumer cần.

## 7. Event flow tối thiểu

| Event logic | Producer → Consumer | Ý nghĩa |
| --- | --- | --- |
| `article.discovered` | Collector → Article | Snapshot nguồn đã thu thập |
| `article.ready` | Article → Intelligence | Evidence normalized cần phân tích |
| `article.duplicate` | Article → Ops/read model | Quan hệ duplicate để truy vết |
| `story.updated` | Intelligence → downstream | Story snapshot/version thay đổi |
| `content.generation.requested` | Intelligence → Generator | Claims cho một Story version |
| `content.draft.created` | Generator → Editorial | Draft đã qua structured validation |
| `publication.published` | Editorial → Public projection | Snapshot xuất bản thành công |

Tên event cuối cùng phải được khóa bằng contract catalog trước implementation;
không silently đổi payload đã có consumer.

## 8. Retry và idempotency

Input retryable có tối đa một retry topic và một DLQ trong MVP. Retry giữ original
event, attempt, next-attempt time và error code đã redact. Consumer deduplicate
bằng event ID, nhưng dùng thêm business key cho Story link, claim, generation và
publication. Offset chỉ được commit sau durable state.
