from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path


class KaggleMetadataBuilder:
    _RESOURCE_SLUG = re.compile(r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$")
    _MODEL_SOURCE = re.compile(
        r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+/\d+$"
    )

    def prepare_kernel(
        self,
        *,
        target: Path,
        runner_source: Path,
        kernel_slug: str,
        dataset_slug: str,
        model_source: str,
    ) -> None:
        self.validate_resource_slug(kernel_slug)
        self.validate_resource_slug(dataset_slug)
        if self._MODEL_SOURCE.fullmatch(model_source) is None:
            raise ValueError("invalid Kaggle model source")
        if target.exists():
            raise FileExistsError(target)
        if not runner_source.is_file():
            raise FileNotFoundError(runner_source)

        target.mkdir(parents=True, mode=0o700)
        runner_target = target / "runner.py"
        shutil.copyfile(runner_source, runner_target)
        os.chmod(runner_target, 0o600)
        metadata = {
            "id": kernel_slug,
            "title": "FootballPulse AI enrichment",
            "code_file": "runner.py",
            "language": "python",
            "kernel_type": "script",
            "is_private": True,
            "enable_gpu": True,
            "enable_tpu": False,
            "enable_internet": False,
            "dataset_sources": [dataset_slug],
            "competition_sources": [],
            "kernel_sources": [],
            "model_sources": [model_source],
        }
        self._write_json(target / "kernel-metadata.json", metadata)

    def write_dataset_metadata(self, *, target: Path, dataset_slug: str) -> None:
        self.validate_resource_slug(dataset_slug)
        required = (target / "manifest.json", target / "articles.jsonl")
        if not all(path.is_file() for path in required):
            raise FileNotFoundError("dataset requires manifest.json and articles.jsonl")
        metadata = {
            "id": dataset_slug,
            "title": "FootballPulse private AI batches",
            "isPrivate": True,
            "licenses": [{"name": "other"}],
        }
        self._write_json(target / "dataset-metadata.json", metadata)

    @classmethod
    def validate_resource_slug(cls, slug: str) -> None:
        if cls._RESOURCE_SLUG.fullmatch(slug) is None:
            raise ValueError("invalid Kaggle resource slug")

    @staticmethod
    def _write_json(path: Path, value: object) -> None:
        path.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.chmod(path, 0o600)
