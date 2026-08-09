from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

RUNNER_PATH = Path(__file__).parents[1] / "kaggle" / "ai-enrichment" / "runner.py"


@pytest.fixture(scope="module")
def runner() -> ModuleType:
    spec = importlib.util.spec_from_file_location("footballpulse_kaggle_runner", RUNNER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runner_parses_json_fence_and_rejects_incomplete_output(runner: ModuleType) -> None:
    parsed = runner.parse_model_json(
        '```json\n{"event_type":"OTHER","summary_en":"Grounded.","claims":[]}\n```'
    )
    assert parsed["event_type"] == "OTHER"

    with pytest.raises(ValueError, match="required"):
        runner.parse_model_json(json.dumps({"summary_en": "Missing fields"}))


def test_runner_discovers_exactly_one_batch_and_qwen_model(
    runner: ModuleType, tmp_path: Path
) -> None:
    dataset = tmp_path / "private-batch"
    dataset.mkdir()
    (dataset / "manifest.json").write_text("{}", encoding="utf-8")
    (dataset / "articles.jsonl").write_text("{}\n", encoding="utf-8")
    model = tmp_path / "qwen-model"
    model.mkdir()
    (model / "config.json").write_text('{"model_type":"qwen3"}', encoding="utf-8")

    assert runner.find_batch_files(tmp_path) == (
        dataset / "manifest.json",
        dataset / "articles.jsonl",
    )
    assert runner.find_model_path(tmp_path) == model


def test_error_record_retains_identity_and_bounds_details(runner: ModuleType) -> None:
    record = runner.error_record(
        {"article_version_id": "article-1", "input_hash": "a" * 64},
        RuntimeError("x" * 2_000),
    )

    assert record["article_version_id"] == "article-1"
    assert record["input_hash"] == "a" * 64
    assert len(record["error"]) == 500


def test_content_chunks_overlap_and_preserve_global_start(runner: ModuleType) -> None:
    content = "zero one two three four five"

    chunks = runner.content_chunks(content, max_words=4, overlap_words=1)

    assert chunks == [(0, "zero one two three"), (13, "three four five")]
