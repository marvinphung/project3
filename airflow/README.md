# FootballPulse Airflow V2

Airflow là orchestrator trung tâm cho pipeline FootballPulse v2.

## 1. DAG chính

`footballpulse_pipeline` là flow production/local chính:

```text
crawl -> entities_extraction -> content_summary -> publish
```

Lịch mặc định: `5,35 * * * *` UTC, cấu hình bằng `FOOTBALLPULSE_V2_PIPELINE_SCHEDULE`.

Các task đều chạy one-shot command qua Docker Compose:

- `crawl`: chạy crawler, ghi `news_metadata` và `news_content` vào MongoDB.
- `entities_extraction`: tạo `filtered_content`, extract canonical entities, ghi `news_entities`.
- `content_summary`: tạo timeline summary 3h UTC cho top 50 entities trong 24h và backfill 7 ngày.
- `publish`: đẩy read model sang Supabase PostgreSQL cho backend/frontend.

## 2. DAG stage thủ công

Các DAG sau vẫn tồn tại để debug/chạy riêng từng stage, nhưng `schedule=None` để tránh chạy trùng với flow chính:

- `footballpulse_crawl`
- `footballpulse_process`
- `footballpulse_summary`
- `footballpulse_publish`

## 3. Execution model

- Airflow dùng metadata DB riêng trong volume `footballpulse_v2_airflow_data`.
- Worker service (`crawler`, `entities-extraction`, `content-summary`, `publisher`) là bounded one-shot commands.
- `catchup=False`, `max_active_runs=1`, retry 2 lần.
- Backend API và frontend không nằm trong Airflow flow; chúng là serving layer đọc PostgreSQL/Supabase.
