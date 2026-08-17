# Chạy FootballPulse trên local

Tài liệu này hướng dẫn khởi động FootballPulse bằng Docker Compose, chạy crawl
và AI flow với dữ liệu thật, theo dõi log và kiểm tra dữ liệu được xuất ra giao
diện.

## 1. Yêu cầu

- Linux hoặc WSL2
- Docker Engine và Docker Compose v2
- Git
- Tối thiểu 8 GB RAM trống; khuyến nghị 16 GB khi chạy model intelligence
- Khoảng 15 GB ổ đĩa cho Docker image, Hugging Face cache và dữ liệu local
- Tài khoản Kaggle có API token nếu chạy AI enrichment thật

Python/Node trên host chỉ cần khi phát triển hoặc chạy test. Luồng ứng dụng chính
có thể chạy hoàn toàn trong Docker.

## 2. Tạo cấu hình môi trường

Từ thư mục gốc repository:

```bash
cp .env.example .env
```

Các giá trị mặc định trong `.env.example` chỉ dành cho máy local. Không dùng lại
password/token này trên server công khai.

Nếu chạy Kaggle thật, điền các biến sau trong `.env`:

```dotenv
FOOTBALLPULSE_AI_PROVIDER=kaggle
FOOTBALLPULSE_KAGGLE_DATASET_SLUG=<kaggle-user>/footballpulse-ai-batches
FOOTBALLPULSE_KAGGLE_KERNEL_SLUG=<kaggle-user>/footballpulse-ai-enrichment
FOOTBALLPULSE_KAGGLE_MODEL_SOURCE=qwen-lm/qwen-3/transformers/0.6b/1
KAGGLE_USERNAME=<kaggle-user>
KAGGLE_API_TOKEN=<kaggle-api-token>
```

Dataset và Notebook/Kernel phải là private resource mà tài khoản trong token có
quyền cập nhật. Không commit `.env` hoặc Kaggle token vào Git.

## 3. Chạy full stack bằng một command

Sau khi đã tạo và điền `.env`, khởi động toàn bộ database, message broker, API,
worker, frontend và Airflow bằng:

```bash
docker compose --profile core --profile app --profile airflow up -d --build
```

Theo dõi toàn bộ tiến trình khởi động:

```bash
docker compose --profile core --profile app --profile airflow logs -f
```

Khi các service ổn định, mở:

- Web App: <http://localhost:8443>
- API health: <http://localhost:8000/health>
- API docs: <http://localhost:8000/docs>
- Crawler health: <http://localhost:8011/health>
- AI Content health: <http://localhost:8002/health>
- Airflow: <http://localhost:8080>

Command full stack sẽ bật cả `crawler-worker` và `ai-enrichment-worker`. Crawler
chạy một lượt rồi thoát; AI worker tiếp tục xử lý các article pending. Nếu dùng
Kaggle, theo dõi log và quota, rồi dừng AI worker khi đã xử lý đủ batch cần thiết:

```bash
docker compose --profile core --profile app stop ai-enrichment-worker
```

## 4. Chạy lần lượt để dễ kiểm tra

Phương án này phù hợp khi chạy lần đầu hoặc cần biết lỗi nằm ở bước nào.

### Bước 1 — Khởi động hạ tầng

Khởi động core dependencies trước:

```bash
docker compose --profile core up -d
```

Kiểm tra container và health:

```bash
docker compose --profile core ps
docker compose --profile core logs -f mongodb postgres kafka redis
```

Các cổng để kết nối từ máy host:

- MongoDB: `mongodb://localhost:27017/?directConnection=true`
- PostgreSQL: `localhost:5432`
- Kafka: `localhost:9092`
- Redis: `localhost:6379`

### Bước 2 — Khởi động API và frontend

Compose profile `app` bao gồm worker. Nếu muốn quan sát từng bước, trước tiên
khởi động migration, API và frontend:

```bash
docker compose --profile core --profile app up -d --build \
  database-migrations crawler-api api-gateway ai-content frontend
```

Xem log:

```bash
docker compose --profile core --profile app logs -f \
  database-migrations crawler-api api-gateway ai-content frontend
```

Kiểm tra bằng trình duyệt:

- Web App: <http://localhost:8443>
- API docs: <http://localhost:8000/docs>
- Crawler API docs: <http://localhost:8011/docs>
- AI Content health: <http://localhost:8002/health>

### Bước 3 — Chạy crawler thật

Chạy crawler và xem log trực tiếp trong terminal hiện tại:

```bash
docker compose --profile core --profile app run --rm crawler-worker
```

Hoặc chạy nền rồi mở terminal khác xem log:

```bash
docker compose --profile core --profile app up -d crawler-worker
docker compose --profile core --profile app logs -f crawler-worker
```

Sau bước này, xem dữ liệu bằng MongoDB Compass tại
`mongodb://localhost:27017/?directConnection=true`, database `footballpulse`,
collection `source_articles`.

### Bước 4 — Chạy intelligence

```bash
docker compose --profile core --profile app up -d intelligence-worker
docker compose --profile core --profile app logs -f intelligence-worker
```

Kết quả nằm ở MongoDB collection `article_intelligence` và PostgreSQL schema
`intelligence_schema`.

### Bước 5 — Chạy AI enrichment thật

```bash
docker compose --profile core --profile app up -d ai-enrichment-worker
docker compose --profile core --profile app logs -f ai-enrichment-worker
```

Theo dõi Notebook trực tiếp tại trang Kaggle Kernel tương ứng với
`FOOTBALLPULSE_KAGGLE_KERNEL_SLUG`. Kết quả local nằm trong MongoDB collections
`article_enrichments`, `ai_batch_jobs` và `ai_enrichment_work`.

### Bước 6 — Chạy Airflow schedule

```bash
docker compose --profile airflow up -d
docker compose --profile airflow logs -f airflow-init airflow-scheduler airflow-api-server
```

Mở Airflow tại <http://localhost:8080>.

### Bước 7 — Kiểm tra public data

```bash
curl --fail 'http://127.0.0.1:8000/api/v1/articles?limit=10&offset=0'
```

Sau khi PostgreSQL có publication, refresh <http://localhost:8443>. Log request
giao diện/API:

```bash
docker compose --profile core --profile app logs -f frontend api-gateway
```

Các container dài hạn phải ở trạng thái `Up`/`healthy`. `database-migrations`,
`mongodb-init` và `crawler-worker` là one-shot container nên `Exited (0)` sau khi
hoàn thành là bình thường.

## 5. Chi tiết crawler thật

Catalog nguồn thật nằm trong `scripts/run-real-crawl.py`. Mỗi nguồn mặc định lấy
tối đa 10 bài, được điều chỉnh bằng `FOOTBALLPULSE_CRAWL_MAX_ARTICLES`.

Chạy một lượt crawler bằng Docker:

```bash
docker compose --profile core --profile app run --rm crawler-worker
```

Theo dõi tiến trình ở terminal khác:

```bash
docker compose --profile core --profile app logs -f crawler-worker
```

Liệt kê catalog mà không crawl:

```bash
docker compose --profile core --profile app run --rm \
  crawler-worker python -u scripts/run-real-crawl.py --list-sources
```

Crawler hiện hỗ trợ các nguồn được cấu hình trong catalog như BBC Sport, The
Guardian, ESPN, Transfermarkt, Sky Sports, AP, Premier League, UEFA và FIFA.
Reuters đang được bỏ qua theo cấu hình hiện tại. Một số website có thể chặn theo
IP, robots policy, JavaScript challenge hoặc thay đổi HTML; lỗi một nguồn không
làm mất các bài đã crawl thành công từ nguồn khác.

## 6. Chi tiết intelligence và AI enrichment

`intelligence-worker` tự đọc Source Article mới trong MongoDB, chạy GLiNER và
BGE, rồi ghi entity/embedding. Xem log bằng:

```bash
docker compose --profile core --profile app logs -f intelligence-worker
```

Khởi động AI worker khi đã sẵn sàng dùng Kaggle:

```bash
docker compose --profile core --profile app up -d ai-enrichment-worker
```

Theo dõi upload dataset, kernel status, download và import:

```bash
docker compose --profile core --profile app logs -f ai-enrichment-worker
```

Các log quan trọng gồm:

- `enrichment_batch_claimed`
- `kaggle_dataset_upload_completed`
- `kaggle_kernel_push_completed`
- `kaggle_job_status_polled`
- `enrichment_results_imported`
- `enrichment_batch_completed`

Khi chỉ cần chạy một số batch và muốn giữ quota, đợi batch hiện tại chuyển sang
`COMPLETED` hoặc `PARTIAL`, sau đó dừng worker:

```bash
docker compose --profile core --profile app stop ai-enrichment-worker
```

Lưu ý: AI output `SUCCESS` chưa đồng nghĩa nội dung được phép publish. Claim phải
qua grounding validation; record `NEEDS_CONTENT_REVIEW` cần editor xử lý thay vì
tự động đưa sang Story.

## 7. Chi tiết Airflow

Airflow dùng để điều phối lịch batch sáu giờ và không bắt buộc cho một lượt chạy
thủ công:

```bash
docker compose --profile airflow up -d
```

Mở <http://localhost:8080> để xem DAG. Các DAG mới được pause mặc định; chỉ bật
khi đã kiểm tra credential và quota của các external provider.

## 8. Mở giao diện và API

- Web App: <http://localhost:8443>
- API Gateway: <http://localhost:8000>
- OpenAPI: <http://localhost:8000/docs>
- Crawler API: <http://localhost:8011>
- AI Content API: <http://localhost:8002>

Smoke check nhanh:

```bash
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8011/health
curl --fail http://127.0.0.1:8002/health
curl --fail 'http://127.0.0.1:8000/api/v1/articles?limit=10&offset=0'
```

Nếu API trả `items: []`, kiểm tra lần lượt: crawler đã ghi Source Article,
intelligence đã hoàn thành, enrichment có claim hợp lệ, Story/timeline đã được
tạo và editorial revision đã được publish. Giao diện public chỉ đọc publication
trong PostgreSQL; nó không hiển thị trực tiếp raw article trong MongoDB.

## 9. Xem log

Xem toàn bộ log chính:

```bash
docker compose --profile core --profile app logs -f \
  crawler-worker intelligence-worker ai-enrichment-worker api-gateway frontend
```

Xem riêng crawl:

```bash
docker compose --profile core --profile app logs -f crawler-worker
```

Xem riêng AI/Kaggle:

```bash
docker compose --profile core --profile app logs -f ai-enrichment-worker
```

Lọc theo batch hoặc article ID:

```bash
docker compose --profile core --profile app logs --no-color | \
  rg '"batch_id":"<batch-id>"'

docker compose --profile core --profile app logs --no-color | \
  rg '"article_version_id":"<article-version-id>"'
```

## 10. Kiểm tra dữ liệu

Mở MongoDB Compass bằng connection string:

```text
mongodb://localhost:27017/?directConnection=true
```

Database ứng dụng mặc định là `footballpulse`. Một số collection quan trọng:

- `source_articles`
- `article_intelligence`
- `article_enrichments`
- `ai_batch_jobs`
- `ai_enrichment_work`

Kiểm tra PostgreSQL bằng CLI trong container:

```bash
docker exec -it footballpulse-postgres-1 \
  psql -U footballpulse -d footballpulse
```

Các schema chính:

- `source_schema`
- `intelligence_schema`
- `content_schema`
- `identity_schema`

Ví dụ kiểm tra public flow:

```sql
SELECT count(*) FROM intelligence_schema.stories;
SELECT count(*) FROM intelligence_schema.timeline_entries;
SELECT count(*) FROM content_schema.editorial_revisions;
SELECT count(*) FROM content_schema.publications;
```

## 11. Lỗi thường gặp

### MongoDB Compass báo `getaddrinfo EAI_AGAIN mongodb`

Tên host `mongodb` chỉ dùng giữa các container trong Docker network. Compass chạy
trên host phải dùng `localhost:27017`, không dùng `mongodb:27017`.

### Compose báo dependency thuộc profile khác

Service ứng dụng phụ thuộc `core`. Dùng đầy đủ profile:

```bash
docker compose --profile core --profile app up -d
```

### Giao diện chạy nhưng không có bài

Kiểm tra public API trước. PostgreSQL phải có `content_schema.publications`; raw
article trong MongoDB không tự động xuất hiện trên trang public.

### Kaggle batch chạy nhưng không tạo Story

Mở `article_enrichments` và kiểm tra `validation_status`, `valid_claims` và
`top_level_errors`. Không bỏ qua validator chỉ để có dữ liệu hiển thị; sửa entity
mapping/prompt hoặc đưa record qua editorial review.

### Website nguồn trả 403, CAPTCHA hoặc timeout

Kiểm tra log theo source. VPN có thể giúp với geo-block nhưng không vượt robots
policy hoặc CAPTCHA. Giữ giới hạn crawl thấp và không tăng concurrency tùy tiện.

## 12. Dừng dự án

Dừng các container nhưng giữ dữ liệu volume:

```bash
docker compose --profile core --profile app --profile airflow down
```

Không thêm `-v` nếu muốn giữ MongoDB, PostgreSQL, Kafka và model cache cho lần
chạy tiếp theo.

## 13. Phát triển và kiểm thử

Cài dependency local bằng `uv` và `pnpm` khi cần sửa code:

```bash
uv sync --all-extras
corepack pnpm --dir frontend install --frozen-lockfile
```

Chạy backend tests và frontend build:

```bash
UV_CACHE_DIR=/tmp/footballpulse-uv-cache uv run pytest -q
corepack pnpm --dir frontend build
```

Xem thêm [Testing](testing.md), [Deployment](deployment.md) và
[Operations Logging](operations-logging.md).
