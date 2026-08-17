from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType, SimpleNamespace

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
    assert runner.MAX_NEW_TOKENS == 512
    assert runner.MAX_INPUT_TOKENS == 4_096
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


def test_compatible_cuda_model_load_uses_float16(runner: ModuleType) -> None:
    fake_torch = SimpleNamespace(
        cuda=SimpleNamespace(
            is_available=lambda: True,
            get_arch_list=lambda: ["sm_70", "sm_80"],
            get_device_capability=lambda _index: (8, 0),
        ),
        float16="float16",
        float32="float32",
    )

    assert runner.model_load_options(fake_torch) == {
        "device_map": "auto",
        "torch_dtype": "float16",
    }


def test_unsupported_cuda_architecture_falls_back_to_cpu(runner: ModuleType) -> None:
    fake_torch = SimpleNamespace(
        cuda=SimpleNamespace(
            is_available=lambda: True,
            get_arch_list=lambda: ["sm_70", "sm_80"],
            get_device_capability=lambda _index: (6, 0),
        ),
        float16="float16",
        float32="float32",
    )

    assert runner.model_load_options(fake_torch) == {
        "device_map": "cpu",
        "torch_dtype": "float32",
    }


def test_claim_offsets_are_recovered_only_from_unique_exact_quote(
    runner: ModuleType,
) -> None:
    claim = {
        "evidence_quote": "Arsenal submitted an offer",
        "evidence_start": 99,
        "evidence_end": 100,
    }

    normalized = runner.normalize_claim_evidence(
        claim,
        "Reports say Arsenal submitted an offer to Real Madrid.",
    )

    assert normalized["evidence_start"] == 12
    assert normalized["evidence_end"] == 38

    with pytest.raises(ValueError, match="unique exact substring"):
        runner.normalize_claim_evidence(claim, "No matching quote exists.")


def test_claim_requires_allowed_predicate_and_canonical_entities(runner: ModuleType) -> None:
    claim = {
        "subject_entity_id": "00000000-0000-4000-8000-000000000001",
        "predicate": "SUBMITTED_BID",
        "object_entity_id": None,
    }
    canonical_ids = {"00000000-0000-4000-8000-000000000001"}

    assert runner.claim_is_canonically_grounded(claim, canonical_ids) is True
    assert (
        runner.claim_is_canonically_grounded(
            {**claim, "predicate": "one allowed article-enrichment.v1 predicate"},
            canonical_ids,
        )
        is False
    )
    assert runner.claim_is_canonically_grounded(claim, set()) is False


def test_prompt_requires_no_claims_without_canonical_entities(runner: ModuleType) -> None:
    prompt = runner.prompt_for(
        {
            "article_version_id": "00000000-0000-4000-8000-000000000001",
            "cleaned_content": "A grounded football report.",
            "canonical_entities": [],
        }
    )

    assert "Return only one concise grounded English summary" in prompt
    assert "subject_entity_id" not in prompt


def test_extract_without_canonical_entities_wraps_model_summary(
    runner: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        runner,
        "generate",
        lambda _tokenizer, _model, _prompt: "  A grounded English summary.  ",
    )

    extracted = runner.extract_chunk(
        object(),
        object(),
        {"cleaned_content": "Evidence.", "canonical_entities": []},
    )

    assert extracted == {
        "event_type": "OTHER",
        "summary_en": "A grounded English summary.",
        "claims": [],
    }
