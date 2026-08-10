from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

MODULE_PATH = Path(__file__).parents[1] / "dags" / "footballpulse_ai_enrichment.py"
SPEC = importlib.util.spec_from_file_location("footballpulse_ai_enrichment", MODULE_PATH)
assert SPEC and SPEC.loader
dag = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dag)


def test_trigger_enrichment_batch_sends_collection_ids() -> None:
    response = MagicMock()
    response.read.return_value = json.dumps({"id": "ai-batch-1"}).encode()
    response.__enter__.return_value = response
    with (
        patch.dict("os.environ", {"FOOTBALLPULSE_AI_INTERNAL_TOKEN": "ai-internal"}),
        patch.object(dag, "urlopen", return_value=response) as urlopen,
    ):
        result = dag.trigger_enrichment_batch(
            ai_url="http://ai-content:8000",
            collection_batch_ids=["crawl-1"],
            window_started_at=datetime(2026, 8, 10, 6, tzinfo=UTC),
        )

    assert result == "ai-batch-1"
    request = urlopen.call_args.args[0]
    assert request.headers["Authorization"] == "Bearer ai-internal"
    assert json.loads(request.data)["collection_batch_ids"] == ["crawl-1"]


def test_poll_enrichment_batch_uses_internal_bearer() -> None:
    response = MagicMock()
    response.read.return_value = json.dumps({"id": "ai-batch-1", "status": "RUNNING"}).encode()
    response.__enter__.return_value = response
    with (
        patch.dict("os.environ", {"FOOTBALLPULSE_AI_INTERNAL_TOKEN": "ai-internal"}),
        patch.object(dag, "urlopen", return_value=response) as urlopen,
    ):
        result = dag.poll_enrichment_batch(ai_url="http://ai-content:8000", batch_id="ai-batch-1")

    assert result["status"] == "RUNNING"
    assert urlopen.call_args.args[0].headers["Authorization"] == "Bearer ai-internal"


def test_wait_for_terminal_batch_is_bounded() -> None:
    with (
        patch.object(dag, "poll_enrichment_batch", side_effect=[{"status": "RUNNING"}]),
        patch.object(dag.time, "sleep"),
    ):
        try:
            dag.wait_for_terminal_batch(
                ai_url="http://ai-content:8000", batch_id="ai-batch-1", max_attempts=1
            )
        except TimeoutError:
            pass
        else:
            raise AssertionError("expected bounded polling timeout")
