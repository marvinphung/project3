# FootballPulse Airflow

`footballpulse_collection` runs at `00:00`, `06:00`, `12:00`, and `18:00` in
`Asia/Ho_Chi_Minh`. It opens one idempotent crawler batch per due source; it
does not create a task per article.

Local configuration:

- `FOOTBALLPULSE_CRAWLER_URL` — crawler base URL.
- `FOOTBALLPULSE_CRAWLER_ADMIN_TOKEN` — bearer token for the crawler admin API.
- `FOOTBALLPULSE_CRAWLER_INTERNAL_TOKEN` — bearer token for the due-source API.

`footballpulse_ai_enrichment` chạy sau collection 30 phút, gửi collection batch
IDs tới `FOOTBALLPULSE_AI_ENRICHMENT_URL`. AI service cần cung cấp endpoint
`POST /internal/v1/enrichment-batches` hiện đã có contract runtime tối thiểu:
trả batch `PREPARING`; trạng thái có thể poll qua
`GET /internal/v1/enrichment-batches/{batch_id}`. Worker/provider execution
vẫn là bước kế tiếp.
