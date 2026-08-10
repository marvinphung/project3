# Thiết kế Story/Claim PostgreSQL — WP 4.1

## Phạm vi

WP 4.1 tạo nền dữ liệu quan hệ cho Story, Claim, evidence, idempotent consumer và
transactional outbox. Source Article và enrichment tiếng Anh đầy đủ vẫn thuộc
MongoDB; PostgreSQL chỉ giữ identity tham chiếu, dữ liệu nghiệp vụ đã chuẩn hóa và
evidence ngắn cần cho audit/API sau này.

WP này chưa thực hiện candidate retrieval, Story matching, confidence algorithm,
timeline snapshot hay Vietnamese projection.

## Mô hình quan hệ

```text
stories
├── story_sources
├── story_entities
└── claims
    └── claim_evidence

processed_events
outbox_events
```

### Story

`stories` là aggregate root. Story có event type, status, confidence score, thời
gian quan sát đầu/cuối và optimistic `version` bắt đầu từ 1. Status MVP gồm:

- `DEVELOPING`: đang có diễn biến mới;
- `CONFIRMED`: có xác nhận đủ mạnh hoặc nguồn chính thức;
- `STALE`: không có Claim mới trong khoảng thời gian cấu hình;
- `CLOSED`: sự kiện đã kết thúc rõ ràng.

`confidence_score` nằm trong `[0, 1]`; WP 4.1 chỉ bảo vệ invariant, chưa tính điểm.

### Source và entity

`story_sources` liên kết Story với `article_version_id` ở MongoDB và giữ metadata
nguồn cần cho truy vấn/audit. Liên kết `(story_id, article_version_id)` là duy nhất.
Không tạo foreign key xuyên database.

`story_entities` liên kết Story với canonical entity theo `entity_id` và loại
`PLAYER`, `CLUB`, `COACH`, `COMPETITION`. Một entity chỉ xuất hiện một lần trong
mỗi Story.

### Claim và evidence

Claim là một phát biểu tiếng Anh đã chuẩn hóa. `claim_fingerprint` được tạo từ:

```text
story_id + subject_entity + predicate + object/value + occurred_at bucket
```

Unique `(story_id, claim_fingerprint)` gom các cách diễn đạt khác nhau của cùng một
diễn biến nhưng vẫn tạo Claim mới khi thông tin nghiệp vụ thay đổi.

`claim_evidence` là quan hệ nhiều-nhiều giữa Claim và StorySource. Nó giữ quote
ngắn cùng `evidence_start`/`evidence_end` trỏ về `cleaned_content` tiếng Anh trong
MongoDB. Unique `(claim_id, story_source_id, evidence_start, evidence_end)` ngăn
evidence bị lặp khi replay.

## Concurrency và event delivery

Mọi update Story dùng `WHERE id = ? AND version = ?`, sau đó tăng `version`. Không
update được row sẽ trả `ConcurrentStoryUpdate` để caller đọc lại và retry.

`processed_events` unique theo `(consumer_name, event_id)`. Worker chỉ ghi dấu đã
xử lý khi thay đổi Story/Claim và outbox cùng commit thành công.

`outbox_events` có trạng thái `PENDING`, `PUBLISHED`, `FAILED` và
`deduplication_key` duy nhất. Việc cập nhật aggregate và tạo outbox event nằm trong
cùng PostgreSQL transaction, tránh trạng thái database đã đổi nhưng Kafka event bị
mất.

## Lựa chọn kiến trúc

Mô hình quan hệ chuẩn hóa được chọn thay cho một JSONB Story document hoặc lưu
aggregate trong MongoDB. Nó cung cấp unique constraint, optimistic locking,
transaction và truy vấn Claim/evidence rõ ràng mà không sao chép raw article sang
PostgreSQL.

## Kiểm thử chấp nhận

- Migration tạo đủ constraint, index và rollback sạch trên PostgreSQL thật.
- Domain model từ chối status/entity type, confidence, fingerprint và evidence
  range không hợp lệ.
- Repository chứng minh unique source/entity/claim/evidence và optimistic update.
- Một transaction ghi Story/Claim, processed-event và outbox nguyên tử.
- Replay cùng event hoặc deduplication key không tạo dữ liệu nghiệp vụ trùng.
