# Kế hoạch demo offline và localhost

## 1. Mục tiêu

Demo không cần Internet, website thật, OpenAI/OpenRouter key hoặc external
images. Tất cả chạy localhost bằng Docker Compose. Không dùng Prometheus hoặc
Grafana.

## 2. Mock News Source

Một service có deterministic clock/scenario state:

### Endpoints dự kiến

- `GET /feeds/{source}.xml`
- `GET /articles/{article_id}`
- `POST /__control/reset`
- `POST /__control/scenarios/{scenario}/advance`
- `POST /__control/failures` để cấu hình failure deterministic
- `GET /health/live`

Control endpoints chỉ expose trong Compose network/demo profile.

### Fixtures

| Stage | Fixture |
| --- | --- |
| 0 | Transfer rumour source A dùng alias `Man Utd` |
| 1 | Source B report cùng event dùng `Manchester United` |
| 2 | Exact duplicate URL có tracking params |
| 3 | Exact duplicate content ở URL/source record khác |
| 4 | Near duplicate thêm chi tiết personal terms |
| 5 | First bid rejected claim |
| 6 | Coach press-conference comment |
| 7 | Official club announcement |
| independent | Injury article cùng club nhưng category khác |
| independent | Match article có hai clubs/competition |

Failure fixtures:

- 429 với `Retry-After`;
- 500 hai lần rồi success;
- slow response dưới timeout;
- response vượt timeout;
- redirect an toàn và redirect tới private IP bị chặn;
- invalid HTML/RSS.

Reset phải tạo cùng titles/bodies/timestamps/IDs để snapshot tests ổn định.

## 3. Mock AI Provider

Provider adapter chạy in-process trong AI Content Service hoặc mock HTTP
container nếu cần contract test:

- `SUCCESS`: stable structured result.
- `INVALID_SCHEMA`.
- `UNSUPPORTED_CLAIM`.
- `RATE_LIMITED_429`.
- `TIMEOUT`.
- `SERVER_ERROR_500`.

Output deterministic theo story/version/prompt. Không gọi external provider khi
`AI_PROVIDER=mock`.

## 4. Docker Compose logical plan

### P0 containers

```text
frontend
api-gateway
crawler-service
article-service
intelligence-service
ai-content-service
content-service
mock-news-source
kafka
mongodb (single-node replica set)
postgres
redis
airflow-api-server
airflow-scheduler
```

Airflow executor/container topology cuối cùng được xác nhận khi phase Airflow
được triển khai. Không dùng Celery/ARQ trong MVP. Kafka UI là optional local
profile; Prometheus/Grafana bị loại khỏi kế hoạch.

### Startup order

1. PostgreSQL/MongoDB/Redis/Kafka health.
2. Init jobs: PostgreSQL roles/schemas, Mongo replica set, Kafka topics.
3. Service migrations theo owner.
4. API/workers/mock source.
5. Airflow metadata migration/bootstrap và scheduler/API server.
6. Frontend sau Gateway readiness.
7. Fixture seed/demo reset.

Compose `depends_on` health không thay application retry; service phải retry
dependency startup có budget và readiness false cho đến khi usable.

### Configuration/secrets

- `.env.example` chỉ safe placeholder.
- `.env` local ignored.
- provider keys optional; mock default.
- internal token/admin demo password được override trong `.env`, không log.
- profile `core`, `demo`, `airflow`, `tools`, `test` để giảm RAM.
- Airflow có metadata DB/schema riêng.

Target command:

```bash
docker compose --profile demo up --build
```

Command này **planned và chưa được xác minh**.

## 5. Demo script

1. Start demo profile; mở frontend, Airflow và optional Kafka UI.
2. Reset scenario.
3. Trigger `footballpulse_demo` hoặc manual crawl.
4. Quan sát admin Sources/Crawl run:
   - concurrent sources;
   - 429/500/timeout attempts;
   - queued counts.
5. Mở Source Articles:
   - primary evidence;
   - exact/URL/near duplicate relationships.
6. Mở Story:
   - aliases resolve một entity;
   - transfer sources vào một story;
   - injury/match tách riêng;
   - claims/timeline/confirmation.
7. Mở Draft Review:
   - mock generation metadata;
   - supporting claims/source refs;
   - edit/approve.
8. Publish hai lần bằng cùng key/parallel commands; xác nhận một publication.
9. Mở public homepage/article/entity/search.
10. Advance official stage; crawl lại; xác nhận same story version/timeline và
    draft update.
11. Demonstrate redelivery/restart:
    - stop Intelligence worker sau durable write trước offset commit qua test
      hook;
    - restart;
    - không tạo duplicate story/claim.
12. Mở Processing Failures, inspect DLQ và retry một replayable failure.

## 6. Demo acceptance checklist

- Demo reset/run có script/documented commands.
- Không có outbound Internet requirement.
- Không có AI credential requirement.
- Story và output deterministic.
- Exact duplicate vẫn traceable nhưng không double-process.
- Near duplicate có thể bổ sung claim/source.
- Official update không tạo story lặp.
- Retry/DLQ/outbox/restart được chứng minh bằng dữ liệu và logs.
- Public/admin frontend dùng API thật, không mock silent fallback.
- Machine/resource settings và elapsed time được ghi, không invent benchmark.
