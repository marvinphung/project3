# FootballPulse

**FootballPulse — Automated Football News Intelligence Platform** là đồ án xây
dựng nền tảng tự động thu thập, hiểu, tổng hợp và xuất bản tin tức bóng đá.
Nhiều bài báo rời rạc được giữ làm bằng chứng, gom vào `Story`, chuyển thành
timeline có mức xác thực và bài tổng hợp qua editorial review.

> Tên đề tài: Thiết kế và xây dựng nền tảng tự động thu thập, tổng hợp và xuất
> bản tin tức bóng đá theo kiến trúc microservices<br>
> Sinh viên: Phùng Minh Vũ — 20235252

## Trạng thái

Các domain/service nền, crawler thật, AI contracts/adapters, Story/timeline,
editorial/publication, API Gateway, React UI và Airflow DAG đã được triển khai ở
mức module. Baseline ngày 2026-08-17 có 381 test pass, Ruff/mypy sạch và frontend
production build thành công. Công việc còn lại tập trung vào runtime wiring:
article → AI enrichment → entity/embedding → Story/timeline, operational Admin
UI và full-stack Docker E2E. Xem
[`completion plan`](docs/plans/2026-08-17-project-completion.md) để theo dõi.

## Python workspace

Yêu cầu Python 3.12 và [`uv`](https://docs.astral.sh/uv/). Thiết lập môi trường
phát triển và chạy quality gates ở repository root:

```bash
uv sync --all-packages --locked
uv run pytest -q
uv run ruff format --check .
uv run ruff check .
uv run mypy
```

Khởi động và kiểm tra các dependency local:

```bash
cp .env.example .env
./scripts/smoke-dependencies.sh
docker compose --env-file .env --profile core down
```

Script có thể chạy lặp lại, không xóa named volumes. Các port chỉ bind vào
`127.0.0.1`; credential trong `.env.example` chỉ dành cho phát triển local.

Chạy migration theo đúng data owner sau khi PostgreSQL healthy:

```bash
uv run alembic -c services/crawler-service/alembic.ini upgrade head
uv run alembic -c services/api-gateway/alembic.ini upgrade head
```

Crawler chỉ được migrate `source_schema`; API Gateway chỉ được migrate
`identity_schema`. Mỗi schema có Alembic version table riêng.

Chạy Crawler Source API sau khi load `.env` và migrate PostgreSQL:

```bash
set -a
source .env
set +a
uv run footballpulse-crawler-service
```

Service mặc định nghe tại `127.0.0.1:8011`; OpenAPI ở `/openapi.json`. Admin và
internal routes dùng hai bearer token riêng trong `.env`.

Root project quản lý workspace và công cụ phát triển; business logic vẫn thuộc
đúng service owner. Không đặt domain logic dùng chung ở root package.

Deterministic test data nằm tại `tests/fixtures/`, gồm RSS/HTML, transport
failures, Kaggle-like JSONL và oracle timeline `00/06/12/18`. Test mặc định chạy
offline, không cần Internet hoặc AI model.

## Invariant trung tâm

```text
Source Article != Story != Generated Article
```

- **Source Article**: evidence bất biến từ một article version của nguồn.
- **Story**: sự kiện bóng đá đang phát triển, có canonical entities, claims,
  confirmation và timeline.
- **Generated Article**: nội dung biên tập song ngữ, chỉ sinh từ supported claims.

## Pipeline local-first

```mermaid
flowchart LR
    A[Airflow mỗi 6 giờ] --> B[RSS allowlist]
    B --> C[Crawl và clean HTML]
    C --> D[MongoDB evidence]
    D --> E[Duplicate + GLiNER + alias + embedding EN]
    E --> F[Kaggle Qwen3-8B batch]
    F --> G[Validate English claims]
    G --> H[pgvector candidates + rule Story matching]
    H --> I[Material Change Detector]
    I -->|Có đổi| J[Timeline EN/VI trong PostgreSQL]
    I -->|Không đổi| K[Chỉ liên kết source]
    J --> L[FastAPI → UI tiếng Việt]
```

English là dữ liệu chuẩn cho AI validation, search, embedding và Story logic.
Vietnamese được materialize trong PostgreSQL để API trả nhanh cho toàn bộ giao
diện. MongoDB giữ raw HTML, cleaned English content, immutable article versions
và enrichment; PostgreSQL giữ source config, entity catalog, Story, claims,
timeline, editorial và public read model.

## Công nghệ mục tiêu

- Python 3.12, FastAPI/Pydantic và sáu backend service.
- Kafka single-node KRaft; Airflow 3 chỉ điều phối batch.
- MongoDB replica set cho evidence; PostgreSQL + pgvector cho product data.
- Redis cho cache/rate limit tạm thời.
- Trafilatura/BeautifulSoup cho HTML extraction.
- GLiNER multi-v2.1 và `bge-small-en-v1.5` chạy local.
- Qwen3-8B 4-bit chạy batch trên Kaggle; Qwen3-4B GGUF local là fallback.
- React/Vite và Docker Compose profiles `core`, `airflow`, `demo`, `tools`.

## Quy tắc timeline

- Pipeline chạy các cửa sổ `00`, `06`, `12`, `18` giờ Việt Nam.
- Chỉ tạo entry khi có claim mới/thay đổi, correction hoặc confirmation đổi.
- Một Story có tối đa một aggregated entry cho mỗi cửa sổ 6 giờ.
- Article mới nhưng không có material change vẫn được lưu/liên kết; timeline
  không thêm dòng.
- Timeline hợp lệ tự hiển thị; Generated Article dài phải qua review/approve.

## Bản đồ tài liệu

| Tài liệu | Nội dung |
| --- | --- |
| [Tổng quan](docs/overview.md) | Tầm nhìn, người dùng và phạm vi |
| [Yêu cầu](docs/requirements.md) | Yêu cầu và tiêu chí chấp nhận |
| [Kiến trúc](docs/architecture.md) | Service, công nghệ, ownership, Airflow/Kafka |
| [Mô hình dữ liệu](docs/data-model.md) | MongoDB/PostgreSQL aggregates và invariants |
| [Story và timeline](docs/story-design.md) | pgvector hybrid matching, claims, cửa sổ 6 giờ |
| [Luồng nội dung](docs/content-flow.md) | Crawl, clean, Kaggle AI, validation và generation |
| [API và event](docs/api-design.md) | Public/admin capabilities và event catalog |
| [Biên tập](docs/editorial-flow.md) | Timeline automation và long-form review/publish |
| [Triển khai](docs/deployment.md) | Local topology, profiles, resources và offline mode |
| [Kiểm thử](docs/testing.md) | Deterministic acceptance, failure và recovery |
| [Logging vận hành](docs/operations-logging.md) | Event, correlation ID, Docker logs và Kaggle progress |
| [Open Questions](docs/open-questions.md) | Các quyết định còn cần benchmark/contract |
| [ADR local-first AI pipeline](docs/decisions/0001-local-first-ai-pipeline.md) | Lý do và hệ quả của thiết kế đã chốt |
| [Implementation plan](docs/plans/2026-08-06-footballpulse-implementation.md) | 9 phase, Work Packages và Collaboration Gates |

## Ngoài MVP

Arbitrary-site crawling, Kubernetes/cloud production, separate vector database,
recommendation, social features, comments, live scores, advanced search cluster,
full multilingual processing và autonomous long-form publication không thuộc MVP.
