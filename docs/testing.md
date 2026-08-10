# Chiến lược kiểm thử

## 1. Mục tiêu

Test phải chứng minh evidence, grounding, Story matching, material change và
recovery. Mặc định chạy deterministic/offline bằng mock RSS và mock Kaggle output;
không cần external model hoặc credential.

## 2. Test layers

| Lớp | Trọng tâm |
| --- | --- |
| Unit | URL/text normalization, hash, article versions, duplicate, alias, claim diff, confirmation |
| Model contract | GLiNER adapter, Qwen input/output JSON schema, evidence/translation validation |
| Event/API contract | Event envelope/version, producer-consumer compatibility, Vietnamese API projection |
| Integration | Mongo transaction/outbox, PostgreSQL+pgvector, Kafka commit/retry/DLQ, concurrency keys |
| End-to-end | Mock RSS → crawl → AI import → Story/timeline → editorial → public UI |
| Load/recovery | Bounded fetch, Kaggle batch size, backpressure, redelivery, restart, simultaneous updates |

Mongo transaction integration test cần replica set local và chỉ thao tác trên
database tạm có tên ngẫu nhiên, sau đó tự xóa:

```bash
FOOTBALLPULSE_RUN_MONGO_INTEGRATION=1 uv run pytest -q \
  services/article-service/tests/test_mongo_article_store_integration.py
```

Test chứng minh index bootstrap chạy lặp, event replay không ghi thêm và unique
outbox conflict rollback cả article lẫn processed-event marker. Duplicate matrix
integration còn chứng minh URL observation, EXACT/NEAR link + outbox decision và
injury/match không bị false positive. Phase Gate 2 nối fixture RSS thật qua cleaner,
artifact handoff và ingestion để kiểm tra số processed observation, immutable
version, duplicate link và outbox trong MongoDB thay vì chỉ test từng đoạn riêng lẻ.

Source repository integration test cũng tạo/xóa database PostgreSQL tạm:

```bash
FOOTBALLPULSE_RUN_SOURCE_INTEGRATION=1 uv run pytest -q \
  services/crawler-service/tests/test_postgres_repositories_integration.py
```

Entity catalog integration test chạy migration/seed trong database tạm, kiểm tra
alias resolution/review, optimistic update, audit và rollback nguyên tử khi alias
đã thuộc entity khác:

```bash
FOOTBALLPULSE_RUN_ENTITY_INTEGRATION=1 uv run pytest -q \
  services/intelligence-service/tests/test_postgres_entity_catalog_integration.py
```

GLiNER mặc định dùng mock và không tải model. Acceptance thật dùng đúng model CPU,
threshold `0.50` và 11 entity trong ba fixture transfer/match/injury:

```bash
FOOTBALLPULSE_RUN_GLINER_ACCEPTANCE=1 uv run \
  --package footballpulse-intelligence-service --extra models --group dev \
  pytest -q -s \
  services/intelligence-service/tests/test_gliner_model_acceptance.py
```

Baseline ngày 2026-08-10 trên máy tham chiếu đạt precision `1.000`, recall `1.000`
(11 true positive/11 predicted/11 expected, không có mention dư). Đây là fixture
nhỏ để khóa adapter và baseline threshold, không phải quality claim cho news corpus
thực; cần mở rộng annotated fixture trước khi đổi model hoặc threshold.

BGE acceptance thật kiểm tra transfer retrieval với injury/match negative controls
và in cold/warm latency cùng peak RSS:

```bash
FOOTBALLPULSE_RUN_BGE_ACCEPTANCE=1 uv run pytest -q -s \
  services/intelligence-service/tests/test_bge_model_acceptance.py
```

Baseline cached ngày 2026-08-10: transfer similarity `0.9600`, injury `0.8170`,
match `0.8075`; cold load + first batch `9.861s`, warm single `0.018s`, warm batch
16 `0.115s`, peak RSS delta khoảng `549 MiB`. Lần chạy đầu gồm tải model mất
`22.946s` và đạt cùng thứ tự similarity. Đây là fixture nhỏ; vector chỉ retrieval
candidate và không thay rule/category merge.

FastAPI TestClient của Starlette 1.6 dùng `httpx2`. Trong Codex sandbox, test
này cần chạy ngoài sandbox vì blocking portal cần thread/event-loop; đây không
phải yêu cầu khi developer chạy trực tiếp trên máy local.

## 3. Acceptance scenario theo cửa sổ

| Window | Input | Kết quả bắt buộc |
| --- | --- | --- |
| 00:00 ngày 1 | Real Madrid đàm phán gia hạn Vinícius | Transfer Story, `REPORTED`, timeline entry |
| 06:00 | Arsenal liên hệ đại diện; một exact duplicate | Same Story, new claim/entry; duplicate không chạy AI |
| 12:00 | Arsenal gửi đề nghị €180m; hai nguồn độc lập | `MULTI_SOURCE`, one aggregated entry, long-form draft |
| 18:00 | Chỉ bài viết lại thông tin cũ | Source được lưu/liên kết; **không có timeline entry** |
| 00:00 ngày 2 | Real Madrid official phủ nhận đã nhận đề nghị | Official denial/correction entry; claim cũ không tự thành `OFFICIAL` |

Các fixture độc lập gồm injury của Vinícius và match Real Madrid–Arsenal; chúng
không được merge vào Transfer Story. Aliases `Vini Jr`, `Vinicius Junior` và
`Vinícius Júnior` phải resolve cùng entity.

Catalog tại `tests/fixtures/mock-news/catalog.json` giữ stable IDs, timestamps,
content hashes, local RSS/HTML paths, transport failures và expected timeline
outcome. `tests/fixtures/ai/` giữ valid, invalid và partial JSONL. Mọi fixture
test chạy offline; thay nội dung HTML bắt buộc cập nhật hash có chủ đích.

Extraction fixtures khóa exact cleaned output cho transfer, injury, match và duplicate.
Assertions kiểm tra fallback/failed diagnostics, loại navigation/script và giữ
nguyên Unicode, punctuation, tỷ số cùng currency như `€180m`.

## 4. AI/Kaggle tests

- `article-enrichment.v1` strict schema từ chối unknown field, enum tự tạo và
  numeric coercion nguy hiểm.
- Bài dài được chunk, claims merge deterministic và evidence quote còn truy được.
- Manifest/article ID/input hash sai bị reject.
- Partial Kaggle output import phần hợp lệ; phần thiếu về `AI_PENDING`.
- Một claim invalid không làm mất claim hợp lệ khác.
- Amount/date/score không có trong evidence bị reject.
- Vietnamese output thêm fact so với English bị flag.
- Vietnamese projection phải giữ claim IDs, entity, amount/currency/date/score,
  negation và certainty anchors.
- Invalid JSON chỉ có một structural repair attempt; JSONL record lỗi không làm
  rollback record hợp lệ khác.
- Kaggle unavailable giữ dữ liệu và retry/fallback đúng policy.
- Mock provider và Kaggle importer dùng cùng output contract.
- Mock fixture lookup fail closed theo article/input hash và bị cấm ngoài
  `test|demo`.
- Local provider test bằng fake runtime: GGUF checksum, lazy load/idle unload,
  concurrency boundary, chunk/repair, timeout isolation và batch limit 20.
- Fallback decision table chứng minh chỉ lỗi hạ tầng allow-list được Kaggle → local;
  integrity/config/programming error không bị che.
- llama.cpp adapter test JSON Schema mode, deterministic temperature, output token
  budget, deadline stopping và fatal native error mà không cần cài model runtime.
- Story/Claim migration test khóa status, confidence/evidence bounds, unique source,
  entity, fingerprint, evidence range, processed event và outbox deduplication.
- PostgreSQL integration test chứng minh atomic create/replay, optimistic update,
  stale-version rollback và rollback marker/outbox cho từng unique-link conflict.
- Kaggle CLI unit test khóa argument array, timeout, redaction và output allow-list.
- Batch importer test partial/missing/unknown/hash mismatch/conflicting duplicate và
  binding của `job-report` với manifest.
- Mongo integration test khóa single-flight lease, atomic status transition và
  idempotent English enrichment persistence:

```bash
FOOTBALLPULSE_RUN_MONGO_INTEGRATION=1 uv run pytest -q \
  services/ai-content-service/tests/test_mongo_batch_repository_integration.py
```

Real Kaggle smoke chỉ chạy khi user duyệt network/quota; báo runtime, quota và chất
lượng output riêng, không gộp với offline test pass/fail.

Local Qwen acceptance cũng opt-in vì cần cài optional native dependency và tải GGUF.
Nó phải báo model checksum, peak RSS, load time, latency/chunk, latency/article và
grounding result; unit suite mặc định không tải hoặc load model.

Event contract suite còn khóa payload bounded cho `article.enriched.v1` và
`article.enrichment.failed.v1`; full summary/evidence/raw output bị cấm trong Kafka.

## 5. Duplicate, Story và timeline tests

- URL/exact duplicate không chạy AI; near duplicate vẫn có thể thêm claim.
- Exact dùng cleaned SHA-256 và chọn primary sớm nhất; near chỉ xét tối đa 50
  candidate trong 72 giờ với trọng số title/content/time `25/65/10`, ngưỡng `0.65`.
- Persisted link phải giữ score components, threshold, reason và identities của
  cả current/primary immutable version.
- Duplicate/syndicated source không nâng `MULTI_SOURCE`.
- Hybrid matching luôn áp hard category filter trước vector candidates.
- Similar injury/transfer embedding không được merge khi category xung đột.
- Concurrent Story create/update không tạo duplicate/lost claim.
- Claim mới, qualifier correction và confirmation change tạo material change.
- Chỉ thay câu chữ summary không tạo material change.
- Unique `(story_id, window_start)` ngăn hai timeline entries cùng window.

## 6. Failure/recovery tests

- 429 tôn trọng `Retry-After`; selected 5xx/timeout retry đúng budget.
- URL credentials, host ngoài allowlist, DNS mixed public/private, unsafe redirect,
  MIME sai và response vượt giới hạn bị chặn.
- RSS malformed có entry hợp lệ được giữ kèm warning; feed không có entry dùng
  được bị fail rõ ràng.
- Global/per-domain concurrency không vượt limit, queue/task count hữu hạn và
  lỗi một source không hủy kết quả source khác; cancellation không bị retry.
- Duplicate Kafka delivery không tạo article/claim/timeline/publication lặp.
- Worker restart sau durable write trước offset commit vẫn giữ invariant.
- Same URL/hash chỉ tạo processed observation; hash mới tạo immutable version và
  `previous_version_id`; outbox chỉ chuyển `PUBLISHED` sau delivery report.
- Invalid event/output không retry vô hạn và đi review/DLQ với redacted context.
- Hai publish đồng thời/cùng idempotency key chỉ tạo một publication.

## 7. API và UI acceptance

Timeline endpoint theo Player/Club/Coach/Competition chỉ trả Vietnamese projection,
đúng thứ tự và pagination/filter. Một timeline row xuất hiện ở nhiều entity page
qua relationship, không copy dữ liệu. Public request không truy MongoDB hoặc gọi
AI. Admin Dashboard drill-down được từ batch tới source/article/enrichment/Story/
timeline/failure.

## 8. Load và quality gates

Load report ghi máy, container limits, source/article counts, worker/partition,
payload/context size, duration, p50/p95/p99, errors và final invariants. Không
invent benchmark. Chạy test hẹp trước rồi broader verification. Python quality
gates dùng các lệnh đã verify trong README; exact frontend, Docker, migration và
E2E commands chỉ được công bố sau khi thực sự được cấu hình và chạy thành công.
