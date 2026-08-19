# FootballPulse Airflow V2

Airflow là scheduler và orchestrator trung tâm duy nhất cho FootballPulse Version 2 local pipeline.

## 1. V2 DAGs

- `footballpulse_crawl` (`*/30 * * * *`):
  Kích hoạt crawl candidates (tối đa 500 candidate/source, 100 fetch/source theo schedule). Khi hoàn tất sẽ trigger `footballpulse_process`.
- `footballpulse_process` (`*/30 * * * *`):
  Xử lý backlog entity và batch Kaggle enrichment. Khi hoàn tất sẽ trigger `footballpulse_publish`.
- `footballpulse_publish` (`*/15 * * * *`):
  Publish các bản ghi đã đạt `VALIDATED` từ MongoDB lên PostgreSQL/Supabase.

## 2. Execution model

- Airflow chạy với `LocalExecutor` và metadata database riêng biệt `footballpulse_airflow` trên PostgreSQL container để không ảnh hưởng tới public read model (`footballpulse_v2`).
- Các worker container (`crawler`, `processor`, `publisher`) là one-shot commands, được kích hoạt theo lượt bounded run bởi Airflow task (không chạy vòng lặp vô tận độc lập).
- Tất cả các DAG có `catchup=False`, `max_active_runs=1`, bounded retries (2 lần), timeout rõ ràng.
