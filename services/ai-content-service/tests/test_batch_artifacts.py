from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from footballpulse_ai_content_service.batch.artifacts import BatchArtifactStore
from footballpulse_ai_content_service.batch.domain import AiBatchStatus
from footballpulse_ai_content_service.contracts.enrichment import ArticleEnrichmentInput

BATCH_ID = UUID("00000000-0000-4000-8000-000000000901")
ARTICLE_ID = UUID("00000000-0000-4000-8000-000000000101")
SOURCE_ID = UUID("00000000-0000-4000-8000-000000000201")


def article_input(*, input_hash: str = "a" * 64) -> ArticleEnrichmentInput:
    return ArticleEnrichmentInput.model_validate(
        {
            "contract_version": "article-enrichment.v1",
            "article_version_id": str(ARTICLE_ID),
            "input_hash": input_hash,
            "title": "Arsenal submit offer for Vinicius Junior",
            "cleaned_content": "Arsenal submitted an offer to Real Madrid.",
            "published_at": "2026-08-01T12:00:00Z",
            "source_id": str(SOURCE_ID),
            "source_reliability_tier": 1,
            "canonical_entities": [],
            "unresolved_mentions": [],
        }
    )


def test_build_writes_deterministic_private_batch_artifacts(tmp_path: Path) -> None:
    store = BatchArtifactStore(tmp_path)

    artifacts = store.build(
        batch_id=BATCH_ID,
        inputs=[article_input()],
        created_at=datetime(2026, 8, 10, 8, 0, tzinfo=UTC),
        model_version="Qwen3-8B-AWQ@revision-1",
        prompt_version="article-enrichment-v1",
    )

    assert artifacts.directory == tmp_path / str(BATCH_ID)
    article_bytes = artifacts.articles_path.read_bytes()
    assert article_bytes.endswith(b"\n")
    assert b"raw_html" not in article_bytes

    manifest_data = json.loads(artifacts.manifest_path.read_text(encoding="utf-8"))
    assert manifest_data["batch_id"] == str(BATCH_ID)
    assert manifest_data["status"] == AiBatchStatus.PREPARING
    assert manifest_data["article_count"] == 1
    assert manifest_data["articles_sha256"] == hashlib.sha256(article_bytes).hexdigest()
    assert manifest_data["records"] == [
        {"article_version_id": str(ARTICLE_ID), "input_hash": "a" * 64}
    ]


def test_build_rejects_duplicate_article_identity(tmp_path: Path) -> None:
    store = BatchArtifactStore(tmp_path)

    with pytest.raises(ValueError, match="duplicate article_version_id"):
        store.build(
            batch_id=BATCH_ID,
            inputs=[article_input(), article_input(input_hash="b" * 64)],
            created_at=datetime(2026, 8, 10, 8, 0, tzinfo=UTC),
            model_version="model",
            prompt_version="prompt",
        )


def test_build_refuses_to_overwrite_an_existing_batch(tmp_path: Path) -> None:
    store = BatchArtifactStore(tmp_path)
    arguments = {
        "batch_id": BATCH_ID,
        "inputs": [article_input()],
        "created_at": datetime(2026, 8, 10, 8, 0, tzinfo=UTC),
        "model_version": "model",
        "prompt_version": "prompt",
    }
    store.build(**arguments)

    with pytest.raises(FileExistsError):
        store.build(**arguments)
