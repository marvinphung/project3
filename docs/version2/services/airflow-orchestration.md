# Airflow Orchestration

## Purpose

Airflow quan ly pipeline 4 buoc cua FootballPulse v2. No chi orchestration data
pipeline, khong nam trong serving path cua nguoi dung.

## DAG

Main DAG:

```text
footballpulse_pipeline
```

Task order:

```text
crawl -> entities_extraction -> content_summary -> publish
```

Default schedule:

```text
FOOTBALLPULSE_V2_PIPELINE_SCHEDULE=5,35 * * * *
```

Neu khong set env, DAG chay phut 5 va 35 moi gio.

## Runtime Model

Airflow task goi Docker Compose commands tren may co Docker daemon:

```text
docker compose -f /workspace/docker-compose.v2.yml run --rm <service> python -m footballpulse_pipeline <command>
```

Vi vay Airflow nen chay tren local/VPS/VM co Docker socket. Khong deploy Airflow
len Render web service neu can Docker Compose orchestration.

## Task Commands

### Crawl

```bash
docker compose -f /workspace/docker-compose.v2.yml run --rm crawler python -m footballpulse_pipeline crawl
```

### Entities extraction

```bash
docker compose -f /workspace/docker-compose.v2.yml run --rm entities-extraction python -m footballpulse_pipeline process
```

### Content summary

```bash
docker compose -f /workspace/docker-compose.v2.yml run --rm content-summary python -m footballpulse_pipeline summary
```

### Publish

```bash
docker compose -f /workspace/docker-compose.v2.yml run --rm publisher python -m footballpulse_pipeline publish
```

## Override Env

Co the override command bang:

- `FOOTBALLPULSE_PIPELINE_CRAWL_COMMAND`
- `FOOTBALLPULSE_PIPELINE_ENTITIES_COMMAND`
- `FOOTBALLPULSE_PIPELINE_SUMMARY_COMMAND`
- `FOOTBALLPULSE_PIPELINE_PUBLISH_COMMAND`

## Data Flow Guarantees

Airflow dam bao thu tu:

1. Crawler tao article docs.
2. Entities extraction tao `filtered_content` va `news_entities`.
3. Content summary tao `entity_timeline_summaries`.
4. Publish dua read model len Supabase PostgreSQL.

Neu mot task fail, cac task downstream cua run do khong nen chay.

## Serving Separation

Backend va frontend khong phu thuoc Airflow trong request path:

```text
frontend -> backend-api -> Supabase PostgreSQL
```

Neu Airflow dung, UI van co the doc du lieu da publish truoc do.

## Operational Notes

- Summary co the ton LLM cost, nen can quan sat log `summary_llm_started`.
- Publish nen chay sau summary de Supabase co timeline moi.
- Neu frontend thieu data, kiem tra thu tu: summary da co trong Mongo chua, publish
  da day sang Supabase chua, backend co doc dung Supabase URL chua.

## Debug Checklist

Neu DAG fail o crawl:

1. Kiem tra source/network/crawler logs.
2. Kiem tra Mongo reachable tu crawler container.
3. Kiem tra Kafka neu crawler publish event.

Neu DAG fail o entities extraction:

1. Kiem tra model download/cache.
2. Kiem tra `NER_DEVICE=cpu` neu may khong co GPU.
3. Kiem tra Mongo documents co `news_content`.

Neu DAG fail o content summary:

1. Kiem tra LLM provider/model/key.
2. Kiem tra timeout/cost.
3. Kiem tra co entity backlog da extract khong.

Neu DAG fail o publish:

1. Kiem tra Supabase URL.
2. Kiem tra PostgreSQL schema da apply.
3. Kiem tra summary docs co `status=COMPLETED`.

## Safe Changes

Co the sua trong Airflow boundary:

- schedule
- task timeout/retry
- command override
- dependency order neu pipeline architecture thay doi

Khong nen sua o day:

- service business logic
- API contract
- frontend routing
