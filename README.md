# FootballPulse

FootballPulse là nền tảng tự động thu thập, tổng hợp và xuất bản tin tức bóng
đá theo kiến trúc microservices. Dự án ưu tiên một pipeline bất đồng bộ,
source-grounded và có thể demo hoàn toàn trên localhost.

## Trạng thái hiện tại

Phase 0 không Docker đã hoàn thành foundation Python, contract
`article.discovered.v1`, typed runtime configuration và deterministic offline
fixture catalog. Chưa có backend service hoặc business logic.

Các file Docker/Compose/init hiện mới là baseline chưa được smoke-test hoàn
chỉnh; theo [ADR-0002](docs/decisions/0002-defer-docker-work.md), mọi công việc
Docker được để tới Phase 4 và chưa phải command được hỗ trợ.

## Yêu cầu

- `uv` 0.12 trở lên.
- `uv` tự cài CPython 3.12 theo `.python-version` khi máy chưa có.
- `pnpm` dành cho frontend hiện hữu.

## Python workspace

Đồng bộ toàn bộ workspace từ lockfile:

```bash
uv sync --all-packages --locked
```

Các command đã được xác minh:

```bash
uv run pytest -q
uv run pytest tests/contract -q
uv run ruff check .
uv run ruff format --check .
uv run mypy packages tests
```

- `packages/event-contracts`: Pydantic runtime model cho event đã version.
- `contracts/events`: JSON Schema Draft 2020-12.
- `packages/runtime-config`: cấu hình env có prefix và secret-safe diagnostics.
- `tests/fixtures/mock-news`: fixture catalog deterministic cho demo/failure.

Không dùng `.env.example` trực tiếp như credential thật. Hai secret bắt buộc
phải được thay bằng giá trị tối thiểu 32 ký tự trước khi service được khởi động.

## Tài liệu

- [Implementation plan](docs/implementation-plan.md)
- [Architecture](docs/architecture.md)
- [Phase 0 foundation ADR](docs/decisions/0001-phase-0-foundation.md)
- [Deferred Docker ADR](docs/decisions/0002-defer-docker-work.md)
- [Port conventions](docs/port-conventions.md)
