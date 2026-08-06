# ADR-0001: Local-first pipeline với Kaggle AI batch

## Status

Accepted

## Date

2026-08-06

## Context

FootballPulse cần chạy chủ yếu trên laptop local, xử lý RSS theo chu kỳ 6 giờ và
demo offline, nhưng local machine không có CUDA/ROCm để chạy model 8B hiệu quả.
Hệ thống cần giữ raw evidence, Story timeline có grounding, giao diện tiếng Việt
và không tạo entry khi dữ liệu không đổi.

## Decision

- Dùng Airflow điều phối batch và Kafka business events cho Python workers.
- RSS được cấu hình trước; crawler lấy HTML, clean và tạo immutable versions.
- MongoDB sở hữu evidence/English enrichment; PostgreSQL+pgvector sở hữu entity,
  Story, claims, bilingual timeline, editorial và API read model.
- GLiNER và English embedding chạy local. Qwen3-8B 4-bit chạy private Kaggle
  batch; Qwen3-4B GGUF local là fallback; mock AI bảo đảm offline demo.
- English là source of truth cho validation/search/matching. Vietnamese được
  materialize trong PostgreSQL chỉ để phục vụ UI/API.
- Hybrid Story matching dùng hard filters, vector candidate retrieval và rule
  scoring. Vector không tự quyết định merge.
- Deterministic Change Detector quyết định material change; tối đa một timeline
  entry cho mỗi Story/cửa sổ 6 giờ và không tạo entry nếu không đổi.
- Compose dùng single-node dependencies và profiles `core`, `airflow`, `demo`,
  `tools`; topology không được mô tả là production-grade.

## Alternatives considered

### Chạy toàn bộ AI local

Đơn giản về data movement nhưng model 8B chậm trên CPU và cạnh tranh RAM với
full Compose stack. Giữ model 4B local chỉ làm fallback.

### Dùng Kaggle cho toàn pipeline

Loại vì quota/network/latency không ổn định và Kaggle không được sở hữu state.
Chỉ offload inference batch; crawl, validation và storage vẫn local.

### Multilingual embedding

Loại khỏi MVP vì English đã là canonical processing language. Vietnamese chỉ
là presentation projection; English-only embedding nhỏ và dễ benchmark hơn.

### Separate vector database

Loại vì pgvector đáp ứng candidate retrieval/search cho quy mô local, giảm một
container và một ownership boundary.

### Airflow task cho từng article

Loại vì scheduler overhead và coupling với Kaggle job. Airflow quản lý batch;
Kafka workers quản lý article events.

## Consequences

- Pipeline vẫn crawl/lưu được khi Kaggle unavailable; AI result có thể chậm sang
  batch sau.
- Private dataset, input hash, partial import và credential hygiene là bắt buộc.
- English/Vietnamese fields cần version/validation để dịch lại không đổi Story.
- Full offline E2E dùng mock AI, còn Kaggle integration cần test riêng có network.
- Threshold, resource limits, model runtime và Airflow executor vẫn phải đo trước
  khi trở thành verified configuration.
