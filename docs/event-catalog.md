# Kafka event catalog

## 1. Naming và envelope

Topic vật lý dùng `<domain>.<event>.v1`; `event_type` không có suffix version.
Schema nằm tại `contracts/events/<event_type>/v1.schema.json`.

```json
{
  "event_id": "uuid",
  "event_type": "article.unique",
  "schema_version": 1,
  "occurred_at": "2026-07-30T03:00:00Z",
  "producer": "article-service",
  "correlation_id": "uuid",
  "causation_id": "uuid-or-null",
  "aggregate_id": "article-id",
  "traceparent": "optional W3C trace context",
  "payload": {}
}
```

Quy tắc version:

- Thêm optional field tương thích có thể giữ version.
- Xóa field, đổi nghĩa/type/required field → topic/schema version mới.
- Consumer validate envelope và payload trước business processing.
- Producer/consumer compatibility được contract test trong CI.
- Không dùng auto-create topic ngoài local bootstrap.

## 2. Event catalog

| Topic / event | Producer → consumer group | Key / ordering | Trigger và payload tối thiểu | Retry / DLQ / idempotency |
| --- | --- | --- | --- | --- |
| `crawl.batch.requested.v1` | Gateway/Crawler → `crawler-service-v1` nếu command chuyển sang async | `batch_id` | batch ID, source IDs, interval, trigger, idempotency key | MVP ưu tiên HTTP command nên topic này P1. Nếu dùng: một retry topic, một DLQ; unique batch idempotency key. |
| `article.discovered.v1` | Crawler → `article-service-v1` | `source_id` để giữ thứ tự source; aggregate là discovery/article ID | source/crawl IDs, original URL/title, publication time, bounded parsed source snapshot, headers allowlist | Retry transient DB/Kafka qua `article.discovered.retry.v1`; DLQ `article.discovered.dlq.v1`; `processed_events.event_id` + article identity. |
| `article.unique.v1` | Article → `intelligence-service-v1` | `article_id` | article ID, source snapshot, normalized title/content/hash, near-duplicate info, publication time | Retry PG/provider-independent failures; DLQ; event ID + unique source article link. |
| `article.duplicate.v1` | Article → `content-readmodel-v1`/ops optional | `primary_article_id` | duplicate ID, primary ID, kind, score/reasons, source info | Không đi intelligence mặc định cho URL/exact; ops consumer idempotent. Near duplicate vẫn đi `article.unique`. |
| `article.processing.failed.v1` | Article → `failure-readmodel-v1` | `article_id` | original event reference, stage, error class/code, attempts | Không retry event thông báo; failure read model upsert theo failure ID. |
| `story.created.v1` | Intelligence → `content-readmodel-v1` | `story_id` | story ID/version/title/category/entities/confirmation/source count | Retry read-model; DLQ; `(story_id, version)` idempotency. |
| `story.updated.v1` | Intelligence → `content-readmodel-v1` | `story_id` | story version, change reasons, new claims/timeline/source/entity snapshots | Per-story ordering required trong partition; reject stale version, reconcile missing gap. |
| `content.generation.requested.v1` | Intelligence/admin command → `ai-content-service-v1` | `story_id` | story ID/version, claim/source snapshots or retrieval reference, prompt version, reason | Provider retry nội bộ bounded; Kafka retry cho infrastructure failure; DLQ; unique generation business key. |
| `content.draft.created.v1` | AI Content → `content-service-v1` | `story_id` | generation job, story/version, validated headline/summary/body, citations/entities, provider metadata | Retry PG; DLQ; unique generation job/draft key. |
| `content.generation.failed.v1` | AI Content → `failure-readmodel-v1` | `generation_job_id` | provider/model, error class, attempts, retry exhausted, redacted context | Idempotent failure ID; manual retry creates new causation event with same business key plus retry generation number. |
| `content.draft.updated.v1` | Content → audit/read-model optional | `draft_id` | draft/revision/status/action actor | `(draft_id, revision, action_id)` unique. |
| `publication.published.v1` | Content → `public-readmodel-v1`, analytics optional | `publication_id` | publication/draft/revision/story IDs, slug, published snapshot/time | Outbox; unique publication ID/idempotency key; DLQ and reconciliation. |
| `processing.failure.recorded.v1` | Mỗi service → `failure-readmodel-v1` | `failure_id` | original envelope, stage, class, attempts, replay policy, redacted error | Không chứa secret/full body; upsert unique failure; operator retry command tạo causation chain. |

Retry topic convention được tạo chỉ cho input topic có transient failure:

```text
<base>.retry.v1
<base>.dlq.v1
```

MVP có tối đa ba delayed attempts ngoài quick in-process retry. Kafka không tự
delay message; bounded retry dispatcher chỉ publish lại khi `next_attempt_at`
đến. Retry giữ cùng `event_id`, tăng `delivery_attempt`, ghi `last_error_code`
đã redaction và dùng exponential backoff có jitter. Hết attempt thì chuyển
sang DLQ; không tạo nhiều delay tier.

## 3. Payload boundaries

- Event không chứa full raw HTML lớn. `article.discovered` có parsed/fetched body
  đã giới hạn cho Milestone 1 để tránh sync API; production refinement có thể
  dùng object reference nhưng không thêm object store vào MVP.
- `article.unique` chứa normalized evidence snapshot đủ cho Intelligence;
  source ID và hash luôn có.
- Generation request chứa structured story claims/source references, không chứa
  arbitrary scraped pages.
- Event failure lưu original envelope khi kích thước an toàn; body lớn được
  redaction/reference.
- Pydantic models là runtime validation; JSON Schema trong `contracts/events`
  là contract chuẩn. Code-generated models không được sửa tay.

## 4. Topic configuration plan

- Replication factor `1` trong localhost single-broker; tài liệu nói rõ không
  chịu được broker loss. Production recommendation là `>=3`, không thuộc MVP.
- Partition bắt đầu 3 cho article/story topics, 1 cho low-volume audit/failure;
  con số được xác nhận qua load test, không tuyên bố throughput trước đo.
- `min.insync.replicas=1` local; producer vẫn `acks=all`.
- Retention đủ cho demo/replay (dự kiến 7 ngày); DLQ dài hơn (30 ngày local nếu
  disk cho phép).
- Compaction chỉ cân nhắc cho read-model snapshot topic P1; business events giữ
  delete retention.

## 5. Consumer groups

Mỗi chức năng có group riêng, không reuse group giữa hai logical consumers:

```text
article-service-v1
intelligence-service-v1
ai-content-service-v1
content-service-v1
content-readmodel-v1
failure-readmodel-v1
```

Scale worker bằng thêm instance cùng group. Một aggregate key luôn đi cùng
partition trong topic để giữ thứ tự **trong topic đó**; không tuyên bố ordering
giữa topic hoặc toàn hệ thống.
