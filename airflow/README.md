# FootballPulse Airflow

`footballpulse_collection` runs at `00:00`, `06:00`, `12:00`, and `18:00` in
`Asia/Ho_Chi_Minh`. It opens one idempotent crawler batch per due source; it
does not create a task per article.

Local configuration:

- `FOOTBALLPULSE_CRAWLER_URL` — crawler base URL.
- `FOOTBALLPULSE_CRAWLER_ADMIN_TOKEN` — bearer token for the crawler admin API.
- `FOOTBALLPULSE_DUE_SOURCE_IDS` — temporary comma-separated source IDs until
  the due-source query is exposed to the scheduler.
