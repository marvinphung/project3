#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

set -a
source .env
set +a

python_bin=".venv/bin/python"
if [[ ! -x "$python_bin" ]]; then
  echo ".venv/bin/python is missing" >&2
  exit 1
fi

echo "[1/5] crawler smoke"
"$python_bin" scripts/smoke-v2-crawler.py

echo "[2/4] entities extraction smoke"
"$python_bin" scripts/smoke-v2-processor.py

echo "[3/4] publisher smoke"
"$python_bin" scripts/smoke-v2-publisher.py

echo "[4/4] api smoke"
"$python_bin" scripts/smoke-v2-api.py

echo "full flow smoke passed"
