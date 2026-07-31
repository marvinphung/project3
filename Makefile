.PHONY: setup test contract-test quality infra-config infra-up infra-smoke infra-down

setup:
	uv sync --all-packages --locked

test:
	uv run pytest -q

contract-test:
	uv run pytest tests/contract -q

quality:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy packages tests

infra-config:
	docker compose config --quiet

infra-up:
	docker compose up -d --wait

infra-smoke:
	./scripts/smoke-infrastructure.sh

infra-down:
	docker compose down
