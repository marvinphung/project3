from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

from footballpulse_ai_content_service.batch.domain import (
    AiBatchManifest,
    AiBatchManifestRecord,
    AiBatchStatus,
)
from footballpulse_ai_content_service.contracts.enrichment import ArticleEnrichmentInput


@dataclass(frozen=True, slots=True)
class BatchArtifacts:
    directory: Path
    manifest_path: Path
    articles_path: Path
    results_path: Path
    report_path: Path


class BatchArtifactStore:
    def __init__(self, root: Path) -> None:
        self._root = root

    def build(
        self,
        *,
        batch_id: UUID,
        inputs: list[ArticleEnrichmentInput],
        created_at: datetime,
        model_version: str,
        prompt_version: str,
    ) -> BatchArtifacts:
        if not inputs:
            raise ValueError("batch requires at least one article")
        article_ids = [item.article_version_id for item in inputs]
        if len(article_ids) != len(set(article_ids)):
            raise ValueError("duplicate article_version_id in batch")

        destination = self._root / str(batch_id)
        if destination.exists():
            raise FileExistsError(destination)

        self._root.mkdir(parents=True, exist_ok=True, mode=0o700)
        staging = self._root / f".{batch_id}.{uuid4().hex}.tmp"
        staging.mkdir(mode=0o700)
        try:
            article_bytes = b"".join(
                (
                    json.dumps(
                        item.model_dump(mode="json"),
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    ).encode("utf-8")
                    + b"\n"
                )
                for item in inputs
            )
            articles_path = staging / "articles.jsonl"
            articles_path.write_bytes(article_bytes)
            os.chmod(articles_path, 0o600)

            manifest = AiBatchManifest(
                contract_version="ai-batch.v1",
                batch_id=batch_id,
                status=AiBatchStatus.PREPARING,
                created_at=created_at,
                model_version=model_version,
                prompt_version=prompt_version,
                article_count=len(inputs),
                articles_sha256=hashlib.sha256(article_bytes).hexdigest(),
                records=tuple(
                    AiBatchManifestRecord(
                        article_version_id=item.article_version_id,
                        input_hash=item.input_hash,
                    )
                    for item in inputs
                ),
            )
            manifest_path = staging / "manifest.json"
            manifest_path.write_text(
                manifest.model_dump_json(indent=2) + "\n",
                encoding="utf-8",
            )
            os.chmod(manifest_path, 0o600)
            staging.rename(destination)
        except BaseException:
            for child in staging.iterdir():
                child.unlink()
            staging.rmdir()
            raise

        return BatchArtifacts(
            directory=destination,
            manifest_path=destination / "manifest.json",
            articles_path=destination / "articles.jsonl",
            results_path=destination / "results.jsonl",
            report_path=destination / "job-report.json",
        )
