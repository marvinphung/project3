#!/usr/bin/env bash
set -euo pipefail

export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/footballpulse-uv-cache}"
repeats="${LOAD_REPEATS:-3}"

for run in $(seq 1 "$repeats"); do
  echo "Offline contract run ${run}/${repeats}"
  /usr/bin/time -f 'elapsed=%E max_rss=%MKB' \
    uv run pytest -q services/api-gateway/tests/test_runtime.py services/api-gateway/tests/test_auth_api.py airflow/tests
done

echo "Offline smoke-load complete; use real infrastructure for throughput/latency benchmarks."
