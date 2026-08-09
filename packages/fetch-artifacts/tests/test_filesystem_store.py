from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import pytest
from footballpulse_fetch_artifacts.filesystem import (
    ArtifactConflictError,
    ArtifactIntegrityError,
    ArtifactMetadata,
    ArtifactProjection,
    FilesystemArtifactStore,
    InvalidArtifactIdError,
)

ARTIFACT_ID = UUID("018f8b45-b634-7c81-a47d-9a7c2f3c2106")
PROJECTION = ArtifactProjection(
    title="Evidence title",
    cleaned_text="Cleaned English evidence text.",
    status="SUCCESS",
    extractor="TRAFILATURA",
    diagnostics=(),
)


def test_atomically_writes_and_reads_bounded_artifact(tmp_path: Path) -> None:
    store = FilesystemArtifactStore(tmp_path, max_content_bytes=100)
    metadata = ArtifactMetadata(
        content_type="text/html",
        etag='"version-1"',
        last_modified="Sun, 09 Aug 2026 00:00:00 GMT",
    )

    stored = store.put(
        ARTIFACT_ID,
        b"<html>evidence</html>",
        metadata=metadata,
        projection=PROJECTION,
    )
    loaded = store.read(ARTIFACT_ID)

    assert loaded.content == b"<html>evidence</html>"
    assert loaded.metadata == stored
    assert loaded.projection == PROJECTION
    assert loaded.metadata.content_length == 21
    assert len(loaded.metadata.content_sha256) == 64
    assert (tmp_path / str(ARTIFACT_ID) / "content.html").is_file()
    assert not list(tmp_path.glob(".tmp-*"))


def test_rejects_non_uuid_identifier_before_building_path(tmp_path: Path) -> None:
    store = FilesystemArtifactStore(tmp_path)

    with pytest.raises(InvalidArtifactIdError):
        store.read(cast(UUID, "../../etc/passwd"))


def test_detects_content_tampering_on_read(tmp_path: Path) -> None:
    store = FilesystemArtifactStore(tmp_path)
    store.put(
        ARTIFACT_ID,
        b"<html>original evidence</html>",
        metadata=ArtifactMetadata(content_type="text/html"),
        projection=PROJECTION,
    )
    (tmp_path / str(ARTIFACT_ID) / "content.html").write_bytes(b"tampered")

    with pytest.raises(ArtifactIntegrityError):
        store.read(ARTIFACT_ID)


def test_same_artifact_id_is_idempotent_only_for_identical_content(tmp_path: Path) -> None:
    store = FilesystemArtifactStore(tmp_path)
    metadata = ArtifactMetadata(content_type="text/html")
    first = store.put(ARTIFACT_ID, b"same content", metadata=metadata, projection=PROJECTION)

    assert (
        store.put(ARTIFACT_ID, b"same content", metadata=metadata, projection=PROJECTION) == first
    )
    with pytest.raises(ArtifactConflictError):
        store.put(
            ARTIFACT_ID,
            b"different content",
            metadata=metadata,
            projection=PROJECTION,
        )


def test_rejects_oversized_artifact_and_unexpected_media_type(tmp_path: Path) -> None:
    store = FilesystemArtifactStore(tmp_path, max_content_bytes=5)

    with pytest.raises(ValueError, match="size"):
        store.put(
            ARTIFACT_ID,
            b"123456",
            metadata=ArtifactMetadata(content_type="text/html"),
            projection=PROJECTION,
        )
    with pytest.raises(ValueError, match="content type"):
        store.put(
            ARTIFACT_ID,
            b"123",
            metadata=ArtifactMetadata(content_type="application/json"),
            projection=PROJECTION,
        )


def test_rejects_metadata_tampering(tmp_path: Path) -> None:
    store = FilesystemArtifactStore(tmp_path)
    store.put(
        ARTIFACT_ID,
        b"<html>evidence</html>",
        metadata=ArtifactMetadata(content_type="text/html"),
        projection=PROJECTION,
    )
    metadata_path = tmp_path / str(ARTIFACT_ID) / "metadata.json"
    document: dict[str, Any] = json.loads(metadata_path.read_text())
    document["content_length"] = 1
    metadata_path.write_text(json.dumps(document))

    with pytest.raises(ArtifactIntegrityError):
        store.read(ARTIFACT_ID)


def test_rejects_unbounded_or_inconsistent_projection(tmp_path: Path) -> None:
    store = FilesystemArtifactStore(tmp_path)

    with pytest.raises(ValueError, match="title"):
        store.put(
            ARTIFACT_ID,
            b"<html>evidence</html>",
            metadata=ArtifactMetadata(content_type="text/html"),
            projection=ArtifactProjection(
                title="x" * 513,
                cleaned_text="text",
                status="SUCCESS",
                extractor="TRAFILATURA",
                diagnostics=(),
            ),
        )
    with pytest.raises(ValueError, match="failed"):
        store.put(
            ARTIFACT_ID,
            b"<html>evidence</html>",
            metadata=ArtifactMetadata(content_type="text/html"),
            projection=ArtifactProjection(
                title="title",
                cleaned_text="text",
                status="FAILED",
                extractor=None,
                diagnostics=("no_content",),
            ),
        )
