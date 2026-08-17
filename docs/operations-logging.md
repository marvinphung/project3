# Logging và theo dõi pipeline

FootballPulse ghi log tiến trình ra `stdout`/`stderr`. Backend dùng JSON một dòng để có thể lọc
theo `event`, `correlation_id`, `batch_id`, `article_version_id` và `story_id`. Kaggle notebook
dùng cùng event name nhưng trình bày dạng dễ đọc trong cell output.

## Xem log Docker

Theo dõi toàn bộ pipeline ứng dụng:

```bash
docker compose logs -f crawler-api crawler-worker intelligence-worker ai-enrichment-worker ai-content api-gateway
```

Theo dõi riêng crawler:

```bash
docker compose logs -f crawler-worker
```

Lọc một batch hoặc article:

```bash
docker compose logs --no-color | rg '"batch_id":"<batch-id>"'
docker compose logs --no-color | rg '"article_version_id":"<article-version-id>"'
```

`FOOTBALLPULSE_LOG_LEVEL` điều khiển mức log và mặc định là `INFO`. Health check không được ghi ở
`INFO` để tránh nhiễu. Docker giữ tối đa năm file log, mỗi file 10 MB, cho các service ứng dụng.

## Event quan trọng

| Stage | Event tiêu biểu |
|---|---|
| Crawl | `crawl_run_started`, `article_fetch_started`, `article_extraction_completed`, `source_completed` |
| Article | `article_event_received`, `article_ingestion_completed`, `article_event_committed` |
| Intelligence | `entity_model_loaded`, `entity_extraction_completed`, `embedding_completed`, `timeline_unchanged` |
| Kaggle | `kaggle_dataset_upload_started`, `kaggle_job_status_polled`, `enrichment_results_imported` |
| Editorial | `editorial_revision_transitioned`, `publication_published` |
| HTTP | `http_request_started`, `http_request_completed`, `rate_limit_exceeded` |

## Kaggle notebook

Notebook `kaggle/ai-enrichment/footballpulse-ai-enrichment.ipynb` in tiến trình tìm input, load
Qwen3, xử lý từng article/chunk và ghi output. Notebook được sinh từ runner production:

```bash
UV_CACHE_DIR=/tmp/footballpulse-uv-cache uv run python scripts/build-kaggle-notebook.py
```

Không sửa logic trực tiếp trong file notebook rồi commit vì lần build tiếp theo sẽ ghi đè nó.

## An toàn dữ liệu

- Không ghi token, password, API key, cookie, authorization header hoặc prompt đầy đủ.
- Không ghi raw HTML, full article content, bản dịch đầy đủ hoặc embedding vector.
- Error log giữ error type và chi tiết đã redaction.
- Frontend không ghi access token; production chỉ giữ warning/error.
