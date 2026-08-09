# Mô hình dữ liệu logic

## 1. Invariant trung tâm

```text
Source Article != Story != Generated Article
```

Source Article là evidence bất biến; Story là sự kiện đang phát triển;
Generated Article là sản phẩm biên tập. Không overwrite evidence bằng AI output
và không dùng bản dịch tiếng Việt làm dữ liệu quyết định nghiệp vụ.

## 2. Data ownership

```mermaid
erDiagram
    SOURCE ||--o{ CRAWL_BATCH : schedules
    SOURCE ||--o{ SOURCE_ARTICLE_VERSION : provides
    SOURCE_ARTICLE_VERSION ||--o{ ARTICLE_ENRICHMENT : enriched_as
    SOURCE_ARTICLE_VERSION ||--o{ DUPLICATE_LINK : participates
    ENTITY ||--o{ ENTITY_ALIAS : has
    STORY }o--o{ ENTITY : tagged_with
    STORY ||--o{ STORY_SOURCE : supported_by
    STORY ||--o{ CLAIM : contains
    STORY ||--o{ TIMELINE_ENTRY : evolves_through
    STORY ||--o{ GENERATED_ARTICLE : generates
    GENERATED_ARTICLE ||--o{ REVISION : has
    REVISION ||--o| PUBLICATION : published_as
```

### MongoDB: evidence và enrichment

#### `source_articles`

Mỗi document là một immutable version:

```json
{
  "_id": "24-hex-mongo-reference",
  "canonical_article_id": "stable-uuidv5-from-canonical-url",
  "article_version_id": "stable-version-uuidv5",
  "version": 2,
  "previous_version_id": "article-version-1",
  "source_id": "bbc-sport",
  "canonical_url": "...",
  "raw_html": "...",
  "raw_content_hash": "sha256",
  "cleaned_content": "English text",
  "content_hash": "sha256",
  "collected_at": "UTC",
  "cleaned_at": "UTC",
  "etag": "optional",
  "last_modified": "optional",
  "extraction_status": "SUCCESS|PARTIAL",
  "duplicate_type": "NONE|EXACT|NEAR",
  "duplicate_of_article_version_id": "optional-primary-version"
}
```

Raw HTML được giữ để reprocess cleaner mà không crawl lại; retention/compression
chỉ được chốt sau khi đo dung lượng.

#### `article_enrichments`

Lưu kết quả theo input/model/prompt version, không overwrite lần chạy cũ:

```json
{
  "_id": "enrichment-456",
  "article_id": "article-version-2",
  "input_hash": "sha256",
  "model": "Qwen3-8B-4bit",
  "prompt_version": "article-enrichment-v1",
  "summary_en": "...",
  "entities": [],
  "claims": [],
  "validation_status": "VALIDATED",
  "processed_at": "UTC"
}
```

MongoDB không cần giữ `summary_vi` làm source of truth. Vietnamese timeline và
content projection được materialize trong PostgreSQL.

#### `duplicate_links`

Mỗi link `EXACT|NEAR` giữ cả `article_id`/`article_version_id` hiện tại và
`primary_article_id`/`primary_article_version_id`, cùng score, các component
`title_similarity`, `content_similarity`, `time_similarity`, threshold, reason
và timestamp. Unique key trên cặp version + loại quan hệ ngăn ghi lặp nhưng vẫn
cho phép audit đúng immutable version. Duplicate vẫn là evidence và không bị xóa.

URL duplicate không tạo version mới nên không có `duplicate_links`; processed
observation giữ `duplicate_type=URL` và reason. Exact primary được chọn
deterministic theo evidence có `collected_at` sớm nhất; near primary là candidate
có weighted score cao nhất trong cửa sổ 72 giờ/tối đa 50 candidate.

#### `processed_events` và `outbox`

`processed_events.event_id` là idempotency marker của consumed event. Marker giữ
`article_id`, `outbox_event_id` và `processed_at`, nhờ đó replay trả lại đúng
identity của lần xử lý đầu thay vì ghi thêm dữ liệu.

`outbox.event_id` là duy nhất; document có `status`, `created_at`, `available_at`
và `publish_attempts` để publisher ở Phase 2 có thể retry có giới hạn. Article
Service ghi các document liên quan trong cùng MongoDB replica-set transaction:

```text
source_articles + optional duplicate_links + processed_events + outbox
→ commit hoặc rollback cùng nhau
```

Nếu event mới có cùng canonical URL và cleaned hash với version mới nhất, service
chỉ ghi processed observation (`UNCHANGED`) và không tạo version/outbox. Nếu hash
đổi, version tăng và giữ `previous_version_id`. Outbox publisher gửi batch tối đa
100, chỉ mark `PUBLISHED` sau Kafka delivery report; crash giữa publish và mark có
thể phát lại cùng event ID và downstream phải idempotent.

Các collection còn lại có unique compound indexes cho article version,
enrichment run và duplicate relationship. Index bootstrap có tên cố định và có
thể chạy lặp mà không tạo index dư.

### PostgreSQL: product và API data

#### Source/crawl

`sources` giữ RSS URL, allowed domains, source type, reliability tier, enabled,
crawl interval/concurrency và operational timestamps. `crawl_batches` và
`crawl_attempts` giữ schedule window, counts, outcome và redacted failure.

Owner migration baseline của Crawler:

```mermaid
erDiagram
    SOURCES ||--o{ CRAWL_BATCHES : schedules
    CRAWL_BATCHES ||--o{ CRAWL_ATTEMPTS : records

    SOURCES {
        uuid id PK
        text rss_url UK
        text[] allowed_domains
        smallint reliability_tier
        boolean enabled
    }
    CRAWL_BATCHES {
        uuid id PK
        uuid source_id FK
        timestamptz window_started_at
        text status
    }
    CRAWL_ATTEMPTS {
        uuid id PK
        uuid batch_id FK
        text article_url
        smallint attempt_number
        text outcome
    }
```

Các bảng trên nằm trong `source_schema`. `identity_schema` hiện chỉ là namespace
và migration history; bảng user/role được hoãn tới Phase 5 để không khóa thiết kế
auth quá sớm. Không có FK hoặc migration xuyên owner.

#### Entity catalog

`entities` có loại `PLAYER|COACH|CLUB|COMPETITION`, canonical name và stable
slug. `entity_aliases` ánh xạ normalized alias tới entity, kèm resolver version,
actor/source và review status. Catalog được seed có kiểm soát và mở rộng qua
Admin review.

#### Story và claims

`stories` giữ category, working headline English, confirmation tổng quan,
fingerprint, English embedding, version và timestamps. `story_entities` và
`story_sources` là link duy nhất; source link chỉ giữ Mongo article ID và bounded
snapshot.

`story_claims` giữ:

```json
{
  "subject_id": "club-arsenal",
  "predicate": "SUBMITTED_BID",
  "object_id": "player-vinicius-junior",
  "qualifiers": {"amount": 180000000, "currency": "EUR"},
  "confirmation": "MULTI_SOURCE",
  "source_article_ids": []
}
```

Claim có stable key từ subject/predicate/object/qualifiers để chống duplicate
delivery. Confirmation thuộc từng claim; Story confirmation chỉ là projection
tổng quan.

#### Timeline

`timeline_entries` giữ một entry tối đa cho mỗi `(story_id, window_start)`:

```json
{
  "story_id": "story-789",
  "window_start": "UTC",
  "window_end": "UTC",
  "summary_en": "Arsenal have submitted ...",
  "summary_vi": "Arsenal đã gửi ...",
  "confirmation": "MULTI_SOURCE",
  "used_claim_ids": [],
  "source_article_ids": [],
  "translation_model": "Qwen3-8B",
  "translation_status": "VALIDATED"
}
```

English là bản chuẩn cho search/change/retranslation; Vietnamese là projection
API đã chuẩn bị sẵn. Nếu không có material change thì không có row cho cửa sổ.

#### Editorial

`generated_articles`, `revisions`, `editorial_actions`, `publications` giữ bản
EN/VI, citation mapping, input Story version, generation metadata và audit.
Publication là immutable snapshot của đúng approved revision.

## 3. AI batch và failures

`ai_batch_jobs` giữ job/crawl batch ID, manifest hash, model/prompt version và
state `PREPARING → UPLOADED → RUNNING → DOWNLOADING → VALIDATING → COMPLETED`.
Partial result được ghi theo article. Failure/review record giữ stage, attempt,
error code, retryability và redacted context; không chứa secret hoặc raw HTML.

## 4. Identity, version và thời gian

- Stable ID không suy ra từ title có thể đổi.
- Timestamp lưu UTC; batch schedule dùng `Asia/Ho_Chi_Minh` và API đổi timezone.
- Article, enrichment, Story, draft và translation đều có version rõ ràng.
- Story/draft dùng optimistic version; publication dùng stable idempotency key.
- Event ID chống delivery lặp; business key chống state nghiệp vụ lặp.

## 5. Invariant dữ liệu

1. Mọi article version truy được về source, crawl batch và previous version.
2. URL/exact duplicate không chạy AI lại; near duplicate vẫn có thể bổ sung claim.
3. Entity trong claim phải canonical hoặc có review state rõ ràng.
4. Evidence quote và factual qualifier phải tồn tại trong cleaned content.
5. Claim confirmation không cao hơn nguồn hỗ trợ; duplicate không là nguồn độc lập.
6. Vector chỉ retrieval, không phải quyết định merge.
7. Không tạo timeline row nếu material change là false.
8. Chỉ một timeline entry cho mỗi Story/window và một successful publication
   cho mỗi revision/idempotency key.
