# Open Questions

Thiết kế pipeline đã được chốt. Các mục dưới đây cần benchmark, contract hoặc
smoke test trước implementation phụ thuộc; không được tự điền bằng giả định.

## 1. Crawl và storage

- Global/per-domain concurrency, timeout, response-size và retry budget cuối cùng?
- Raw HTML compression/retention bao lâu trên ổ local?
- Crawler bàn giao raw HTML cho Article Service qua artifact store/API nào để
  `fetch_artifact_id` không phụ thuộc shared local path và Kafka không chứa body?
- Source-specific cleaner/parser nào cần thiết sau khi thử RSS thực tế?
- Cách xác định syndicated source independence ngoài exact hash?

## 2. AI/Kaggle

- Batch article/token limit nào phù hợp Kaggle quota/runtime thực tế?
- Qwen3-8B 4-bit format/runtime nào vượt benchmark chất lượng và thời gian?
- Khi nào dùng Qwen3-4B local fallback thay vì đợi batch sau?
- Prompt/schema version đầu tiên và repair budget cho invalid JSON?
- Ngưỡng GLiNER/alias confidence nào bắt buộc review?

## 3. Story và vector

- `bge-small-en-v1.5` có đạt acceptance trên football fixtures hay cần model khác?
- pgvector index type/config sau khi có dataset size và load measurement?
- Rule weights, candidate count, category time windows và create/review thresholds?
- Policy hạ confirmation và cách thể hiện conflicting claims?
- `OFFICIAL_ANNOUNCEMENT` classification chi tiết cho update thuộc category khác?

## 4. Timeline và editorial

- Khi nhiều correction trong cùng cửa sổ, summary policy ưu tiên/diễn đạt thế nào?
- Translation validator tự động tới mức nào trước khi cần editor?
- Stale approved draft được rebase, regenerate hay bắt buộc review lại?
- Correction/unpublish/supersede cho publication đã phát hành?
- Citation public ở cấp câu, đoạn hay danh sách nguồn?

## 5. API và frontend

- Cursor encoding và default page size cho timeline/article endpoints?
- Story timeline public expose full entry hay editorial projection rút gọn?
- Admin UI cho entity resolution/Story merge nằm trong MVP tới mức nào?
- SEO metadata tối thiểu cho React/Vite không SSR?

## 6. Local deployment và verification

- Airflow 3 local executor nào vượt smoke test với resource budget của máy?
- Kafka partition/retention, Docker memory/CPU limits và full-stack idle footprint?
- Redis outage policy cho rate limit/cache cụ thể?
- Exact build, migration, startup, integration, E2E và demo commands sau khi chạy
  xác minh?
- SLO local nào đáng đo cho crawl-to-timeline và API visibility?

## 7. Cách đóng câu hỏi

Quyết định ảnh hưởng nhiều service hoặc khó đảo ngược phải có ADR. Threshold và
resource number phải kèm fixture/benchmark. Contract/API/event thay đổi cần test
compatibility; không silently cập nhật payload đã có consumer.
