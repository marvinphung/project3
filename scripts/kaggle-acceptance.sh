#!/usr/bin/env bash
set -euo pipefail

export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/footballpulse-uv-cache}"

uv run pytest -q services/ai-content-service/tests/test_kaggle_cli.py \
  services/ai-content-service/tests/test_provider_config.py \
  services/ai-content-service/tests/test_provider_router.py

if [[ "${RUN_KAGGLE_ACCEPTANCE:-0}" != "1" ]]; then
  echo "Kaggle live acceptance skipped (set RUN_KAGGLE_ACCEPTANCE=1 to enable)."
  exit 0
fi

command -v kaggle >/dev/null || { echo "kaggle CLI is required" >&2; exit 1; }
kaggle --version
kaggle datasets list --mine --page-size 1 >/dev/null
echo "Kaggle API acceptance passed."
