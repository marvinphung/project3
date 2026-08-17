# Yêu cầu hệ thống

## 1. Thu thập và evidence

- Admin quản lý RSS URL, allowed domains, source type/reliability, enabled state
  và crawl policy trong PostgreSQL.
- Airflow tạo crawl batch lúc `00:00`, `06:00`, `12:00`, `18:00` theo Việt Nam.
- Collector lấy URL từ RSS rồi tải HTML với global/per-domain concurrency hữu hạn.
- Trafilatura trích nội dung; BeautifulSoup fallback theo source.
- Newline/tab/control character được normalize an toàn; dấu câu, tiền tệ và số
  liệu phải được giữ.
- Mỗi thay đổi content tạo immutable article version; raw HTML và cleaned English
  text được lưu MongoDB.
- URL/exact duplicate không chạy AI; near duplicate vẫn được enrichment.

## 2. Local intelligence và AI batch

- GLiNER local nhận diện Player/Club/Coach/Competition.
- Alias resolver chỉ trả canonical ID từ catalog hoặc review state.
- `bge-small-en-v1.5` tạo English embedding; không embed Vietnamese.
- AI Content Service tạo private JSONL Kaggle batch với manifest/input hash.
- Qwen3-0.6B Transformers xử lý `chunk → claims → merge → summary`; Qwen3-4B local và
  mock provider dùng cùng contract.
- Partial Kaggle result được import; phần thiếu về `AI_PENDING`.
- Mọi claim phải có evidence quote, canonical/unresolved entity, controlled
  predicate và certainty hợp lệ.
- English là source of truth; Vietnamese output không được thêm fact.

## 3. Story và timeline

- Candidate retrieval: hard category/time filter → pgvector top candidates →
  deterministic rule scoring.
- Vector không tự quyết định attach/merge.
- Confirmation được tính theo từng claim; duplicate/syndicated source không là
  hai nguồn độc lập.
- Material Change Detector, không phải LLM, quyết định tạo timeline.
- Claim mới/thay đổi, correction hoặc confirmation change là material change.
- Không có material change thì chỉ liên kết article; không tạo timeline entry.
- Một Story có tối đa một aggregated entry mỗi cửa sổ 6 giờ.
- Timeline PostgreSQL giữ `summary_en` và `summary_vi`; API public trả Vietnamese.

## 4. Editorial và web

- Timeline đã grounded/validated có thể tự động hiển thị; output lỗi vào review.
- Long-form draft được tạo ở milestone quan trọng hoặc theo editor request và
  luôn qua `DRAFT → NEEDS_REVIEW → APPROVED/REJECTED → PUBLISHED`.
- Public API cung cấp timeline theo Player, Club, Coach, Competition và Story.
- UI request chỉ đọc PostgreSQL read model, không query MongoDB hoặc gọi AI.
- Admin Dashboard drill-down batch → source → article → enrichment → Story →
  timeline/failure.

## 5. Phi chức năng

| Thuộc tính | Yêu cầu MVP |
| --- | --- |
| Correctness | Không nâng certainty, không tạo unsupported fact/translation |
| Reliability | At-least-once, idempotent consumers, bounded retry, DLQ/review |
| Concurrency | Queue, fetch, Kafka, DB, AI và fallback concurrency đều bounded |
| Security | Source allowlist/SSRF protection; Kaggle dataset private; secret không commit |
| Traceability | Batch/correlation/causation/article/story IDs và audit history |
| Local-first | Một máy Compose; single-node dependency; resource usage được đo |
| Offline | Mock RSS/Kaggle/AI; không cần Internet/model credential trong demo |
| Observability | Health/readiness, structured logs, operational read models |

## 6. Quyền truy cập

- Public read không cần token.
- `EDITOR`: evidence/claims review, draft edit/approve/reject.
- `ADMIN`: thêm source/crawl/retry, alias/Story admin và publish.
- Internal API dùng configured service identity trong local Compose network.

## 7. Acceptance criteria

1. Full mock pipeline đi từ RSS tới Vietnamese entity timeline/publication.
2. Aliases `Vini Jr`, `Vinicius Junior`, `Vinícius Júnior` về cùng Player.
3. Exact duplicate không chạy Kaggle; near duplicate có thể thêm claim.
4. 00/06/12 windows tạo đúng Story updates; 18h không đổi không tạo entry.
5. Hai nguồn độc lập nâng `MULTI_SOURCE`; duplicate không nâng.
6. Official denial/correction tạo update nhưng không biến claim cũ thành official.
7. Injury và match không merge vào transfer dù có cùng entity.
8. Partial Kaggle output, duplicate event và restart không làm mất/nhân đôi state.
9. Hai publish đồng thời/cùng key chỉ có một publication.

## 8. Ràng buộc

- Ba tuần, ưu tiên một vertical slice hoàn chỉnh.
- Python 3.12 cho backend; React/Vite hiện có được giữ.
- Local machine không có CUDA/ROCm; AI mạnh chạy Kaggle, fallback 4B dùng CPU.
- Không thêm separate vector database/search cluster hoặc hạ tầng production.
