# 🚀 Hướng Dẫn Vận Hành & Chạy Dự Án FootballPulse (Version 2)

Tài liệu này hướng dẫn chi tiết toàn bộ các kịch bản chạy hệ thống **FootballPulse v2**, từ chạy tự động All-in-One với Docker Compose, chạy từng service theo luồng (Pipeline Flow) bằng Docker, cho đến chạy và kiểm thử (debug) trực tiếp từng service trên **Localhost bằng `python3`**.

---

## 📋 MỤC LỤC

1. [Yêu Cầu Môi Trường (Prerequisites)](#1-yêu-cầu-môi-trường-prerequisites)
2. [Cấu Hình Biến Môi Trường (.env)](#2-cấu-hình-biến-môi-trường-env)
3. [Kịch Bản 1: Chạy FULL Dự Án Trong 1 Command Duy Nhất (All-in-One Docker)](#3-kịch-bản-1-chạy-full-dự-án-trong-1-command-duy-nhất-all-in-one-docker)
4. [Kịch Bản 2: Hướng Dẫn Chạy Lần Lượt Các Service Theo Flow Bằng Docker](#4-kịch-bản-2-hướng-dẫn-chạy-lần-lượt-các-service-theo-flow-bằng-docker)
5. [Kịch Bản 3: Hướng Dẫn Chạy Lần Lượt Từng Service Bằng Localhost với Python3 (Test & Debug Mode)](#5-kịch-bản-3-hướng-dẫn-chạy-lần-lượt-từng-service-bằng-localhost-với-python3-test--debug-mode)
6. [Kiểm Tra Dữ Liệu Trong Database & API](#6-kiểm-tra-dữ-liệu-trong-database--api)
7. [Dừng & Reset Toàn Bộ Hệ Thống](#7-dừng--reset-toàn-bộ-hệ-thống)

---

## 1. Yêu Cầu Môi Trường (Prerequisites)

- **Hệ điều hành**: Linux (Ubuntu/Debian), macOS, hoặc Windows (WSL2).
- **Docker Engine**: v24.0+ và **Docker Compose**: v2.20+.
- **Python**: v3.12+ (kèm `uv` package manager nếu chạy local).
- **Node.js**: v18+ và `npm` (dành cho Frontend).

---

## 2. Cấu Hình Biến Môi Trường (.env)

Tạo file `.env` từ `.env.example` tại thư mục gốc của repository:

```bash
cp .env.example .env
```

Các biến môi trường quan trọng:

```ini
# Cấu hình môi trường chung
FOOTBALLPULSE_ENV=local
FOOTBALLPULSE_LOG_LEVEL=INFO

# Cổng dịch vụ Local
FOOTBALLPULSE_KAFKA_PORT=19092
FOOTBALLPULSE_MONGODB_PORT=27117
FOOTBALLPULSE_POSTGRES_PORT=15432
FOOTBALLPULSE_API_PORT=8000
FOOTBALLPULSE_AIRFLOW_PORT=8080

# Cấu hình kết nối MongoDB Replica Set Local
FOOTBALLPULSE_MONGODB_URL="mongodb://127.0.0.1:27117/?replicaSet=rs0&directConnection=true"
FOOTBALLPULSE_MONGODB_DB=footballpulse_v2
FOOTBALLPULSE_V2_MONGODB_URL="mongodb://127.0.0.1:27117/?replicaSet=rs0&directConnection=true"
FOOTBALLPULSE_V2_MONGODB_DB=footballpulse_v2

# Cấu hình kết nối Kafka Local
FOOTBALLPULSE_V2_KAFKA_BOOTSTRAP_SERVERS=127.0.0.1:19092

# Cấu hình kết nối PostgreSQL Local
FOOTBALLPULSE_POSTGRES_HOST=127.0.0.1
FOOTBALLPULSE_POSTGRES_PORT=15432
FOOTBALLPULSE_POSTGRES_DB=footballpulse_v2
FOOTBALLPULSE_POSTGRES_USER=footballpulse
FOOTBALLPULSE_POSTGRES_PASSWORD=footballpulse_v2_local
FOOTBALLPULSE_V2_POSTGRES_URL=postgresql+psycopg://footballpulse:footballpulse_v2_local@127.0.0.1:15432/footballpulse_v2

# Cấu hình Kaggle AI Enrichment (Chạy LLM trên Kaggle GPU)
FOOTBALLPULSE_KAGGLE_DATASET_SLUG=your-username/footballpulse-ai-batches
FOOTBALLPULSE_KAGGLE_KERNEL_SLUG=your-username/footballpulse-ai-enrichment
FOOTBALLPULSE_KAGGLE_MODEL_SOURCE=qwen-lm/qwen-3/transformers/0.6b/1
KAGGLE_USERNAME=your-kaggle-username
KAGGLE_API_TOKEN=your-kaggle-api-token
FOOTBALLPULSE_KAGGLE_ACCELERATOR=NvidiaTeslaT4
```

---

## 3. Kịch Bản 1: Chạy FULL Dự Án Trong 1 Command Duy Nhất (All-in-One Docker)

Đây là cách nhanh nhất để khởi động toàn bộ hạ tầng, pipeline và API Gateway backend.

### 3.1. Lệnh khởi động 1-Click:

```bash
docker compose -f docker-compose.v2.yml up -d --build
```

### 3.2. Toàn bộ các dịch vụ được khởi tạo:
1. `mongodb`: MongoDB 7 với Replica Set `rs0` (Cổng `27117`).
2. `mongodb-init`: Tự động khởi tạo Replica Set cho MongoDB.
3. `kafka`: Apache Kafka 4.3 chạy KRaft Mode (Cổng `19092`).
4. `postgres`: PostgreSQL 17 + tiện ích mở rộng `pgvector` (Cổng `15432`).
5. `api`: FastAPI Gateway Backend phục vụ REST API `/api/v2` (Cổng `8000`).
6. `airflow-init`: Khởi tạo và migrate schema cho cơ sở dữ liệu Airflow.
7. `airflow-scheduler`: Bộ lập lịch tự động kích hoạt pipeline.
8. `airflow-dag-processor`: Bộ phân tích và tải DAGs.
9. `airflow-webserver`: Giao diện quản trị Airflow API Server (Cổng `8080`).

### 3.3. Kiểm tra trạng thái các container:

```bash
docker compose -f docker-compose.v2.yml ps
```

### 3.4. Khởi động Frontend Web:

Mở một terminal mới:

```bash
cd frontend
npm install
npm run dev
```
👉 Truy cập giao diện người dùng tại: **[http://localhost:5173](http://localhost:5173)**

### 3.5. Theo dõi Logs & Kích hoạt Pipeline tự động (Airflow):

- **Xem log API Gateway**:
  ```bash
  docker compose -f docker-compose.v2.yml logs -f api
  ```
- **Xem log Airflow Scheduler**:
  ```bash
  docker compose -f docker-compose.v2.yml logs -f airflow-scheduler
  ```
- **Kích hoạt thủ công toàn bộ chuỗi Pipeline qua Airflow**:
  ```bash
  docker compose -f docker-compose.v2.yml exec -T airflow-scheduler airflow dags trigger footballpulse_crawl
  ```

---

## 4. Kịch Bản 2: Hướng Dẫn Chạy Lần Lượt Các Service Theo Flow Bằng Docker

Khi bạn muốn kiểm soát chính xác từng bước trong luồng xử lý dữ liệu (Crawl ➡️ Process/AI ➡️ Publish ➡️ Serve API) bằng Docker containers:

```text
  [Hạ tầng DB/Kafka]
         │
         ├───► Bước 1: Crawler Service (Cào tin & bắn Kafka event)
         ├───► Bước 2: Processor Service (Trích xuất Entity & Kaggle AI Enrichment)
         ├───► Bước 3: Publisher Service (Materialize sang PostgreSQL)
         ├───► Bước 4: API Gateway (Khởi động REST API)
         └───► Bước 5: Frontend UI (Khởi động giao diện)
```

### Bước 4.1: Khởi động Hạ tầng cơ sở dữ liệu & Message Broker

```bash
docker compose -f docker-compose.v2.yml up -d mongodb mongodb-init kafka postgres
```
*Đợi khoảng 10-15 giây để MongoDB replica set, Kafka và Postgres đạt trạng thái `healthy`.*

Kiểm tra:
```bash
docker compose -f docker-compose.v2.yml ps
```

---

### Bước 4.2: Chạy Crawler Service (Flow 1 - Ingestion)

Crawler hiện tại chạy theo 2 pha:

- `Step 1 - discovery`: đọc RSS/sitemap/listing HTML, lọc theo domain và tuổi bài, rồi seed `news_metadata`.
- `Step 2 - content`: lấy các record chưa có `news_content`, fetch/extract nội dung, lưu content và chỉ khi thành công mới publish `news.crawled.v1`.

Chạy toàn bộ flow:

```bash
docker compose -f docker-compose.v2.yml run --rm crawler \
  python -m footballpulse_pipeline crawl --source "The Guardian Football" --source "BBC Sport Football" --max-articles 5
```

Một số lệnh debug hữu ích:

```bash
docker compose -f docker-compose.v2.yml run --rm crawler \
  python -m footballpulse_pipeline crawl --list-sources

docker compose -f docker-compose.v2.yml run --rm crawler \
  python -m footballpulse_pipeline crawl --step discovery --max-age-days 30

docker compose -f docker-compose.v2.yml run --rm crawler \
  python -m footballpulse_pipeline crawl --step content --max-articles 10 --concurrency 6
```

---

### Bước 4.3: Chạy Processor Service & AI Enrichment (Flow 2 - Processing)

Đọc sự kiện từ Kafka, trích xuất Entity bóng đá (CLB, Cầu thủ, Giải đấu) và đẩy batch lên Kaggle GPU để tóm tắt / trích xuất claims:

```bash
docker compose -f docker-compose.v2.yml run --rm processor \
  python -m footballpulse_pipeline process --limit 10
```

---

### Bước 4.4: Chạy Publisher Service (Flow 3 - Materialization)

Đọc các bản ghi đã `VALIDATED` từ MongoDB và materialize sang bảng public của PostgreSQL:

```bash
docker compose -f docker-compose.v2.yml run --rm publisher \
  python -m footballpulse_pipeline publish --limit 20
```

---

### Bước 4.5: Khởi động API Gateway Backend (Flow 4 - Serving)

Khởi động backend server đọc dữ liệu từ PostgreSQL:

```bash
docker compose -f docker-compose.v2.yml up -d api
```

Kiểm tra API hoạt động:
```bash
curl -s http://127.0.0.1:8000/health
curl -s "http://127.0.0.1:8000/api/v2/articles?limit=5"
```

---

### Bước 4.6: Khởi động Frontend Web (Flow 5 - Client)

```bash
cd frontend
npm install
npm run dev
```
👉 Mở trình duyệt tại **[http://localhost:5173](http://localhost:5173)** để xem tin tức đã được crawl và hiển thị.

---

## 5. Kịch Bản 3: Hướng Dẫn Chạy Lần Lượt Từng Service Bằng Localhost với Python3 (Test & Debug Mode)

> 🎯 **Mục đích**: Chạy trực tiếp mã nguồn bằng `python3` trên máy host (localhost) giúp bạn dễ dàng đặt `breakpoint`, debug logic, xem stacktrace chi tiết và kiểm tra lỗi của từng service mà không cần tốn thời gian rebuild Docker image mỗi khi sửa code.

---

### Bước 5.1: Cấu hình Kafka Host & Port ra Localhost

Khi Python chạy trực tiếp trên máy Host kết nối vào Kafka trong Docker, Kafka cần advertise địa chỉ ra ngoài host `localhost:19092` hoặc `127.0.0.1:19092`.

1. **Kiểm tra cấu hình Kafka trong `docker-compose.v2.yml`**:
   Đảm bảo container Kafka đã mở port và khai báo `PLAINTEXT_HOST`:
   ```yaml
   kafka:
     image: apache/kafka:4.3.1
     ports:
       - "127.0.0.1:19092:9092"
     environment:
       KAFKA_LISTENERS: PLAINTEXT://:29092,CONTROLLER://:29093,PLAINTEXT_HOST://:9092
       KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:29092,PLAINTEXT_HOST://localhost:19092
       KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT
   ```

2. **Kiểm tra cấu hình trong file `.env` trên máy host**:
   ```ini
   FOOTBALLPULSE_V2_KAFKA_BOOTSTRAP_SERVERS=127.0.0.1:19092
   FOOTBALLPULSE_MONGODB_URL="mongodb://127.0.0.1:27117/?replicaSet=rs0&directConnection=true"
   FOOTBALLPULSE_MONGODB_DB=footballpulse_v2
   FOOTBALLPULSE_POSTGRES_HOST=127.0.0.1
   FOOTBALLPULSE_POSTGRES_PORT=15432
   FOOTBALLPULSE_POSTGRES_USER=footballpulse
   FOOTBALLPULSE_POSTGRES_PASSWORD=footballpulse_v2_local
   FOOTBALLPULSE_POSTGRES_DB=footballpulse_v2
   FOOTBALLPULSE_V2_POSTGRES_URL=postgresql+psycopg://footballpulse:footballpulse_v2_local@127.0.0.1:15432/footballpulse_v2
   ```

3. **Khởi động các dịch vụ hạ tầng (Database & Message Broker)**:
   ```bash
   docker compose -f docker-compose.v2.yml up -d --build mongodb mongodb-init kafka postgres
   ```
   *Kiểm tra các container hạ tầng đã UP và healthy:*
   ```bash
   docker compose -f docker-compose.v2.yml ps
   ```

---

### Bước 5.2: Chuẩn bị môi trường Python Localhost

Tại thư mục gốc dự án:

```bash
# Đồng bộ môi trường và dependencies bằng uv (khuyên dùng):
uv sync --all-packages --all-extras --group dev

# Kích hoạt virtual environment:
source .venv/bin/activate

# Xuất biến môi trường từ .env:
set -a
source .env
set +a
```

---

### Bước 5.3: Chạy lần lượt từng Service bằng `python3` theo Pipeline Flow

#### 1️⃣ Bước 1: Chạy & Test Crawler Service bằng `python3`
Crawler local hiện chạy theo 2 bước tách biệt trong cùng command:

- `discovery`: seed `news_metadata` cho bài mới từ source catalog.
- `content`: crawl backlog chưa có `news_content`, extract text và publish `news.crawled.v1` sau khi save content thành công.

```bash
python3 -m footballpulse_pipeline crawl --source "The Guardian Football" --source "BBC Sport Football" --max-articles 5
```

Chạy riêng từng pha khi cần debug:

```bash
python3 -m footballpulse_pipeline crawl --list-sources
python3 -m footballpulse_pipeline crawl --step discovery --max-age-days 30
python3 -m footballpulse_pipeline crawl --step content --max-articles 10 --concurrency 6
```

Lưu ý:

- `--max-age-days` mặc định là `30` để bỏ qua bài quá cũ.
- `--max-articles` áp vào backlog content fetch của Step 2.
- `FOOTBALLPULSE_CRAWL_MODE=bootstrap` sẽ tăng giới hạn fetch Step 2 từ `100` lên `500`.

*(Hoặc chạy script kiểm tra nhanh crawler: `python3 scripts/smoke-v2-crawler.py`)*

#### 2️⃣ Bước 2: Chạy & Test Processor & AI Enrichment bằng `python3`
Consume event từ Kafka `127.0.0.1:19092`, trích xuất Entity và đẩy batch AI:

```bash
python3 -m footballpulse_pipeline process --limit 10
```
*(Hoặc chạy script kiểm tra nhanh processor: `python3 scripts/smoke-v2-processor.py` & `python3 scripts/smoke-v2-enrichment.py`)*

#### 3️⃣ Bước 3: Chạy & Test Publisher Service bằng `python3`
Đồng bộ các bài viết `VALIDATED` từ MongoDB sang PostgreSQL:

```bash
python3 -m footballpulse_pipeline publish --limit 20
```
*(Hoặc chạy script kiểm tra nhanh publisher: `python3 scripts/smoke-v2-publisher.py`)*

#### 4️⃣ Bước 4: Chạy & Test API Gateway Backend bằng `python3`
Khởi động FastAPI Gateway trực tiếp trên máy host:

```bash
PYTHONPATH=packages/pipeline/src:packages/runtime-config/src:packages/event-contracts/src:services/api-gateway/src:services/content-service/src:services/ai-content-service/src:services/crawler-service/src:services/intelligence-service/src:services/publisher-service/src python3 -m footballpulse_api_gateway.runtime_v2
```
*(Hoặc kiểm tra nhanh API endpoints: `python3 scripts/smoke-v2-api.py`)*

#### 5️⃣ Bước 5: Chạy Frontend Client
Mở một cửa sổ terminal mới:

```bash
cd frontend
npm install
npm run dev
```

---

### Bước 5.4: Chạy Toàn Bộ Bộ Kiểm Thử Tự Động (One-Click Local Smoke Test)

Dự án cung cấp sẵn script kiểm tra tự động liên hoàn toàn bộ 5 bước trên môi trường Localhost:

```bash
bash scripts/smoke-v2-full-flow.sh
```

Nếu tất cả các bước hiển thị `passed`, hệ thống của bạn hoàn toàn sẵn sàng và không có lỗi!

---

## 6. Kiểm Tra Dữ Liệu Trong Database & API

### 6.1. Kiểm tra MongoDB (Dữ liệu thô và AI Enrichment):

```bash
docker compose -f docker-compose.v2.yml exec -T mongodb mongosh --quiet --eval '
const v2 = db.getSiblingDB("footballpulse_v2");
print("--- THỐNG KÊ MONGODB V2 ---");
print("1. Số bài viết metadata:       " + v2.news_metadata.countDocuments());
print("2. Số bài viết có full content:" + v2.news_content.countDocuments());
print("3. Số bài viết đã trích entity:" + v2.news_entities.countDocuments());
print("4. Số bài viết AI Validated:   " + v2.news_enrichments.countDocuments({validation_status: "VALIDATED"}));
'
```

### 6.2. Kiểm tra PostgreSQL (Public Read Model):

```bash
docker compose -f docker-compose.v2.yml exec -T postgres psql -U footballpulse -d footballpulse_v2 -c '
SELECT 
  (SELECT count(*) FROM sources) as sources_count,
  (SELECT count(*) FROM articles) as articles_count,
  (SELECT count(*) FROM stories) as stories_count,
  (SELECT count(*) FROM publications) as publications_count;
'
```

### 6.3. Kiểm tra API Gateway Endpoints:

- **Kiểm tra sức khỏe API**:
  ```bash
  curl -s http://127.0.0.1:8000/health
  ```
- **Lấy danh sách bài viết mới nhất**:
  ```bash
  curl -s "http://127.0.0.1:8000/api/v2/articles?limit=5"
  ```
- **Lấy danh sách thực thể bóng đá**:
  ```bash
  curl -s "http://127.0.0.1:8000/api/v2/entities?limit=10"
  ```

---

## 7. Dừng & Reset Toàn Bộ Hệ Thống

- **Dừng các container (giữ nguyên dữ liệu)**:
  ```bash
  docker compose -f docker-compose.v2.yml down
  ```
- **Dừng và xóa toàn bộ dữ liệu (Reset sạch sẽ Database & Kafka)**:
  ```bash
  docker compose -f docker-compose.v2.yml down -v
  ```
- **Xóa cache và file build tạm**:
  ```bash
  rm -rf .tmp .local-data/fetch-artifacts .footballpulse/ai-batches
  ```
