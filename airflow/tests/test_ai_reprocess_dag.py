from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

MODULE_PATH = Path(__file__).parents[1] / "dags" / "footballpulse_ai_reprocess.py"
SPEC = importlib.util.spec_from_file_location("footballpulse_ai_reprocess", MODULE_PATH)
assert SPEC and SPEC.loader
dag = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dag)


def test_reprocess_is_manual_and_bounded() -> None:
    responses = iter(
        [
            {"id": "ai-1"},
            {"id": "ai-1", "status": "RUNNING"},
            {"id": "ai-1", "status": "COMPLETED"},
        ]
    )
    with patch.object(dag, "_request", side_effect=lambda *args, **kwargs: next(responses)):
        result = dag.reprocess_batch(
            ai_url="http://ai-content:8000",
            collection_batch_ids=["crawl-1"],
            window_started_at=datetime(2026, 8, 10, 6, tzinfo=UTC),
        )
    assert result["status"] == "COMPLETED"
