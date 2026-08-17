from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

MODULE_PATH = Path(__file__).parents[1] / "dags" / "footballpulse_collection.py"
SPEC = importlib.util.spec_from_file_location("footballpulse_collection", MODULE_PATH)
assert SPEC and SPEC.loader
dag = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dag)

NOW = datetime(2026, 8, 10, 6, tzinfo=UTC)


def test_batch_idempotency_key_is_stable() -> None:
    assert dag.batch_idempotency_key("source-1", NOW) == "source-1:2026-08-10T06:00:00+00:00"


def test_fetch_due_source_ids_uses_internal_bearer() -> None:
    response = MagicMock()
    response.read.return_value = json.dumps({"items": [{"id": "source-1"}]}).encode()
    response.__enter__.return_value = response
    with (
        patch.dict("os.environ", {"FOOTBALLPULSE_CRAWLER_INTERNAL_TOKEN": "internal"}),
        patch.object(dag, "urlopen", return_value=response) as urlopen,
    ):
        result = dag.fetch_due_source_ids(crawler_url="http://crawler:8000", at=NOW)

    assert result == ["source-1"]
    request = urlopen.call_args.args[0]
    assert request.full_url.startswith("http://crawler:8000/internal/v1/sources/due?")
    assert request.headers["Authorization"] == "Bearer internal"


def test_trigger_crawler_batches_sends_stable_key() -> None:
    response = MagicMock()
    response.read.return_value = json.dumps({"id": "batch-1"}).encode()
    response.__enter__.return_value = response
    with (
        patch.dict("os.environ", {"FOOTBALLPULSE_CRAWLER_ADMIN_TOKEN": "admin"}),
        patch.object(dag, "urlopen", return_value=response) as urlopen,
    ):
        result = dag.trigger_crawler_batches(
            crawler_url="http://crawler:8000", source_ids=["source-1"], window_started_at=NOW
        )

    assert result == ["batch-1"]
    request = urlopen.call_args.args[0]
    assert json.loads(request.data) == {"idempotency_key": "source-1:2026-08-10T06:00:00+00:00"}
