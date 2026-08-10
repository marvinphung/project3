#!/usr/bin/env bash
set -euo pipefail

export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/footballpulse-uv-cache}"

echo "[1/4] API gateway/content contract tests"
uv run pytest -q services/api-gateway/tests services/content-service/tests

echo "[2/4] AI batch lifecycle"
uv run pytest -q services/ai-content-service/tests/test_api.py

echo "[3/4] Airflow HTTP orchestration contracts"
uv run pytest -q airflow/tests

echo "[4/4] Compose contract"
uv run pytest -q tests/infrastructure/test_compose_contract.py

echo "Offline demo checks passed."
