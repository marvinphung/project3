# Final handoff checklist

## Đã kiểm tra offline

- API gateway/content contract tests
- AI batch lifecycle
- Airflow collection/enrichment/reprocess contracts
- Compose profile rendering
- Kaggle provider contract

Chạy nhanh:

```bash
./scripts/offline-demo.sh
./scripts/kaggle-acceptance.sh
LOAD_REPEATS=5 ./scripts/measure-load.sh
```

## Cần kiểm tra khi có infrastructure

- PostgreSQL/MongoDB/Kafka/Redis health và migrations
- Airflow scheduler chạy thật và trigger Collection DAG
- Kaggle live acceptance
- Browser build/E2E frontend
- Throughput, p95 latency, memory và restart/concurrency benchmark

Không coi kết quả offline là production capacity measurement.
