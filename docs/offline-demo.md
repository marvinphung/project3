# Offline demo

Chạy từ repository root:

```bash
./scripts/offline-demo.sh
```

Demo không cần Kafka, MongoDB, PostgreSQL, Airflow hoặc internet. Nó kiểm tra
các contract bằng in-memory repository, ASGI transport, mock HTTP và Compose
rendering. Đây là smoke demo cho logic, không thay thế integration/E2E với
local infrastructure thật.
