from __future__ import annotations

import json
from pathlib import Path

import pytest
from footballpulse_ai_content_service.batch.metadata import KaggleMetadataBuilder


def test_metadata_is_private_offline_and_contains_only_approved_sources(tmp_path: Path) -> None:
    runner = tmp_path / "runner.py"
    runner.write_text("print('runner')\n", encoding="utf-8")
    target = tmp_path / "kernel"

    KaggleMetadataBuilder().prepare_kernel(
        target=target,
        runner_source=runner,
        kernel_slug="owner/footballpulse-ai",
        dataset_slug="owner/footballpulse-batches",
        model_source="qwen/qwen3/transformers/8b-awq/1",
    )

    metadata = json.loads((target / "kernel-metadata.json").read_text(encoding="utf-8"))
    assert metadata["is_private"] is True
    assert metadata["enable_internet"] is False
    assert metadata["enable_gpu"] is True
    assert metadata["dataset_sources"] == ["owner/footballpulse-batches"]
    assert metadata["model_sources"] == ["qwen/qwen3/transformers/8b-awq/1"]
    assert (target / "runner.py").read_text(encoding="utf-8") == "print('runner')\n"


def test_metadata_rejects_public_kernel_or_invalid_slugs(tmp_path: Path) -> None:
    runner = tmp_path / "runner.py"
    runner.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="slug"):
        KaggleMetadataBuilder().prepare_kernel(
            target=tmp_path / "kernel",
            runner_source=runner,
            kernel_slug="not-a-slug",
            dataset_slug="owner/dataset",
            model_source="owner/model/framework/variation/1",
        )


def test_dataset_metadata_declares_private_resource(tmp_path: Path) -> None:
    target = tmp_path / "dataset"
    target.mkdir()
    (target / "manifest.json").write_text("{}", encoding="utf-8")
    (target / "articles.jsonl").write_text("{}\n", encoding="utf-8")

    KaggleMetadataBuilder().write_dataset_metadata(
        target=target,
        dataset_slug="owner/footballpulse-batches",
    )

    metadata = json.loads((target / "dataset-metadata.json").read_text(encoding="utf-8"))
    assert metadata == {
        "id": "owner/footballpulse-batches",
        "title": "FootballPulse private AI batches",
        "isPrivate": True,
        "licenses": [{"name": "other"}],
    }
