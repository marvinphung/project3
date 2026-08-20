from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.extend(
    [
        str(ROOT / "services/api-gateway/src"),
        str(ROOT / "packages/runtime-config/src"),
    ]
)

from footballpulse_api_gateway.runtime_v2 import build_app


def _load_repo_env() -> dict[str, str]:
    env = dict(os.environ)
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            env.setdefault(key.strip(), val.strip().strip('"').strip("'"))
    return env


def main() -> None:
    env = _load_repo_env()
    app = build_app(env)
    client = TestClient(app)

    # 1. Test top entities endpoint
    top_res = client.get("/api/v2/entities/top?limit=10")
    if top_res.status_code != 200:
        raise AssertionError(f"top entities failed: {top_res.status_code} {top_res.text}")
    top_items = top_res.json()["items"]

    # 2. Test search endpoint
    search_res = client.get("/api/v2/entities/search?q=Arsenal")
    if search_res.status_code != 200:
        raise AssertionError(f"search failed: {search_res.status_code} {search_res.text}")

    # 3. If any entities exist, test timeline endpoint
    if top_items:
        first_entity_id = top_items[0]["id"]
        timeline_res = client.get(f"/api/v2/entities/{first_entity_id}/timeline")
        if timeline_res.status_code != 200:
            raise AssertionError(f"timeline failed: {timeline_res.status_code} {timeline_res.text}")
        print(f"v2 api smoke passed: top_count={len(top_items)} sample_entity={top_items[0]['canonical_name']}")
    else:
        print("v2 api smoke passed (database has 0 entities currently)")


if __name__ == "__main__":
    main()

