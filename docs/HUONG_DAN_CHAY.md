# Hướng Dẫn Vận Hành & Chạy Dự Án FootballPulse (Version 2)

Tài liệu này hướng dẫn chi tiết cách khởi động, vận hành và kiểm tra toàn bộ hệ thống **FootballPulse v2** (Local Pipeline thực tế, tích hợp Airflow 3, Kafka, MongoDB Replica Set, Kaggle GPU AI Enrichment, PostgreSQL Read Model, Backend API Gateway và Frontend).

---

## 1. Yêu Cầu Môi Trường (Prerequisites)

- **Hệ điều hành**: Linux / macOS / Windows (WSL2).
- **Docker & Docker Compose**: Docker Engine v24+ và Docker Compose v2+.
- **Node.js**: v18+ và npm (dành cho Frontend).
- **Python**: v3.12+ (nếu muốn chạy dev cục bộ).

---

## 2. Cấu Hình Biến Môi Trường (.env)

Tạo file `.env` từ `.env.example` tại thư mục gốc của dự án:

```bash
cp .env.example .env
```

Các biến môi trường quan trọng cần lưu ý trong `.env`:

```ini
# Cấu hình chung
FOOTBALLPULSE_ENV=local
FOOTBALLPULSE_LOG_LEVEL=INFO

# Cổng dịch vụ Local
FOOTBALLPULSE_KAFKA_PORT=19092
FOOTBALLPULSE_MONGODB_PORT=27117
FOOTBALLPULSE_POSTGRES_PORT=15432
FOOTBALLPULSE_API_PORT=8000
FOOTBALLPULSE_AIRFLOW_PORT=8080

# Thông tin Kaggle GPU AI Enrichment (Chạy thật trên Kaggle)
FOOTBALLPULSE_KAGGLE_DATASET_SLUG=pmv259/footballpulse-ai-batches
FOOTBALLPULSE_KAGGLE_KERNEL_SLUG=pmv259/footballpulse-ai-enrichment
FOOTBALLPULSE_KAGGLE_MODEL_SOURCE=qwen-lm/qwen-3/transformers/0.6b/1
KAGGLE_USERNAME=pmv259
KAGGLE_API_TOKEN=KGAT_b2aa9813070479c8946a25c95f1a82df
FOOTBALLPULSE_KAGGLE_ACCELERATOR=NvidiaTeslaT4
```

---

## 3. Khởi Động Toàn Bộ Hệ Thống (Docker Compose)

Chạy lệnh sau tại thư mục gốc của repository để build và khởi động toàn bộ các container:

```bash
docker compose -f docker-compose.v2.yml up -d --build
```

### Kiểm tra trạng thái các container:

```bash
docker compose -f docker-compose.v2.yml ps
```

Các container cốt lõi sẽ hoạt động:
1. `footballpulse-v2-postgres-1`: PostgreSQL 17 + pgvector (cổng `15432`).
2. `footballpulse-v2-mongodb-1`: MongoDB 7 Replica Set `rs0` (cổng `27117`).
3. `footballpulse-v2-kafka-1`: Apache Kafka 4.3 (cổng `19092`).
4. `footballpulse-v2-airflow-scheduler-1`: Airflow Scheduler điều phối chuỗi DAG.
5. `footballpulse-v2-airflow-dag-processor-1`: Airflow DAG Processor phân tích DAGs.
6. `footballpulse-v2-airflow-webserver-1`: Airflow API Server / Webserver (cổng `8080`).
7. `footballpulse-v2-api-1`: FastAPI Gateway Backend (cổng `8000`).

---

## 4. Hướng Dẫn Vận Hành Với Apache Airflow 3

Hệ thống sử dụng **Apache Airflow 3** làm bộ điều phối tự động duy nhất (Single Orchestrator).

### 4.1. Truy cập Airflow
- **Airflow API Server & Swagger Docs**: [http://127.0.0.1:8080/docs](http://127.0.0.1:8080/docs)
- **Health Check**: [http://127.0.0.1:8080/health](http://127.0.0.1:8080/health)

### 4.2. Danh sách các DAGs tự động
- `footballpulse_crawl`: Thu thập dữ liệu từ các trang tin bóng đá hàng đầu (BBC, Guardian, Sky Sports, Premier League,...). Khi chạy xong sẽ tự động kích hoạt `footballpulse_process`.
- `footballpulse_process`: Trích xuất Entities, phát sự kiện Kafka, tạo batch đẩy lên Kaggle GPU để tóm tắt và sinh claims. Khi chạy xong sẽ tự động kích hoạt `footballpulse_publish`.
- `footballpulse_publish`: Đọc dữ liệu đã `VALIDATED` từ MongoDB và materialize vào bảng public của PostgreSQL.

### 4.3. Kích hoạt DAG thủ công qua CLI:

```bash
# Trigger toàn bộ chuỗi Pipeline bắt đầu từ Crawl:
docker compose -f docker-compose.v2.yml exec -T airflow-scheduler airflow dags trigger footballpulse_crawl

# Kiểm tra danh sách các lần chạy của DAG:
docker compose -f docker-compose.v2.yml exec -T airflow-scheduler airflow dags list-runs footballpulse_crawl
docker compose -f docker-compose.v2.yml exec -T airflow-scheduler airflow dags list-runs footballpulse_process
docker compose -f docker-compose.v2.yml exec -T airflow-scheduler airflow dags list-runs footballpulse_publish
```

---

## 5. Chạy Trực Tiếp Từng Bước (Manual CLI)

Nếu muốn chạy trực tiếp từng giai đoạn để quan sát log chi tiết:

### Bước 1: Crawl tin tức (Crawler)
```bash
# Crawl 5 bài báo mỗi nguồn từ các nguồn thực tế:
docker compose -f docker-compose.v2.yml run --rm crawler \
  python -m footballpulse_pipeline crawl --max-articles 5

# Hoặc chỉ định rõ nguồn cần crawl:
docker compose -f docker-compose.v2.yml run --rm crawler \
  python -m footballpulse_pipeline crawl --source "The Guardian Football" --source "BBC Sport Football" --max-articles 3
```

### Bước 2: Xử lý thực thể & Kaggle AI Enrichment (Processor)
```bash
# Xử lý các bài viết mới từ Kafka / MongoDB và kích hoạt Kaggle batch:
docker compose -f docker-compose.v2.yml run --rm processor \
  python -m footballpulse_pipeline process --limit 10
```

### Bước 3: Xuất bản vào PostgreSQL Read Model (Publisher)
```bash
# Materialize các bài viết đã VALIDATED sang PostgreSQL:
docker compose -f docker-compose.v2.yml run --rm publisher \
  python -m footballpulse_pipeline publish --limit 20
```

---

## 6. Kiểm Tra Dữ Liệu Trong Database

### 6.1. MongoDB (Dữ liệu thô và AI Enrichment)
Kết nối vào MongoDB bằng `mongosh`:
```bash
docker compose -f docker-compose.v2.yml exec -T mongodb mongosh --quiet --eval '
const v2 = db.getSiblingDB("footballpulse_v2");
print("--- THỐNG KÊ MONGODB V2 ---");
print("Số bài viết metadata:      " + v2.news_metadata.countDocuments());
print("Số bài viết có content:    " + v2.news_content.countDocuments());
print("Số bài viết đã tách entity:" + v2.news_entities.countDocuments());
print("Số bài viết AI Validated:  " + v2.news_enrichments.countDocuments({validation_status: "VALIDATED"}));
'
```

### 6.2. PostgreSQL (Public Read Model)
Truy vấn bảng trong PostgreSQL:
```bash
docker compose -f docker-compose.v2.yml exec -T postgres psql -U footballpulse -d footballpulse_v2 -c '
SELECT 
  (SELECT count(*) FROM sources) as sources_count,
  (SELECT count(*) FROM articles) as articles_count,
  (SELECT count(*) FROM stories) as stories_count,
  (SELECT count(*) FROM publications) as publications_count;
'
```

---

## 7. Kiểm Tra API Gateway Backend

Backend API Gateway chạy tại cổng `8000`:

- **Kiểm tra trạng thái Liveness**:
  ```bash
  curl -s http://127.0.0.1:8000/health
  ```
  *Kết quả mong đợi:* `{"service":"api-gateway","status":"ok"}`

- **Lấy danh sách bài báo đã xuất bản**:
  ```bash
  curl -s "http://127.0.0.1:8000/api/v2/articles?limit=5"
  ```

- **Lấy chi tiết 1 bài báo qua slug**:
  ```bash
  curl -s "http://127.0.0.1:8000/api/v2/articles/<article-slug>"
  ```

- **Lấy nguồn trích dẫn của bài báo**:
  ```bash
  curl -s "http://127.0.0.1:8000/api/v2/articles/<article-slug>/sources"
  ```

- **Lấy dòng sự kiện (Timeline) của story**:
  ```bash
  curl -s "http://127.0.0.1:8000/api/v2/stories/<story-id>/timeline"
  ```

- **Lấy danh sách các thực thể bóng đá**:
  ```bash
  curl -s "http://127.0.0.1:8000/api/v2/entities?limit=10"
  ```

---

## 8. Khởi Động Giao Diện Frontend

Frontend được xây dựng bằng **React + Vite**:

1. Di chuyển vào thư mục `frontend`:
   ```bash
   cd frontend
   ```
2. Cài đặt dependencies:
   ```bash
   npm install
   ```
3. Chạy môi trường phát triển:
   ```bash
   npm run dev
   ```
4. Truy cập giao diện tại: **[http://localhost:5173](http://localhost:5173)** (hoặc URL hiển thị trên terminal).

---

## 9. Dừng Hoặc Khởi Động Lại Hệ Thống

- **Dừng toàn bộ hệ thống**:
  ```bash
  docker compose -f docker-compose.v2.yml down
  ```
- **Dừng và xóa toàn bộ dữ liệu (Reset sạch sẽ)**:
  ```bash
  docker compose -f docker-compose.v2.yml down -v
  ```
- **Xem logs của một dịch vụ cụ thể**:
  ```bash
  docker compose -f docker-compose.v2.yml logs -f api
  docker compose -f docker-compose.v2.yml logs -f airflow-scheduler
  ```
