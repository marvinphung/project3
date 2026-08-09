from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

_ALLOWED_CONTENT_TYPES = {"text/html", "application/xhtml+xml"}
_METADATA_LIMIT_BYTES = 4096
_PROJECTION_LIMIT_BYTES = 1_100_000
_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")


class ArtifactStoreError(Exception):
    """Base error for the local artifact handoff boundary."""


class InvalidArtifactIdError(ArtifactStoreError, ValueError):
    """Raised before path construction for a non-UUID artifact identity."""


class ArtifactNotFoundError(ArtifactStoreError):
    """Raised when an opaque artifact reference is unavailable."""


class ArtifactConflictError(ArtifactStoreError):
    """Raised when one artifact identity is reused for different evidence."""


class ArtifactIntegrityError(ArtifactStoreError):
    """Raised when persisted content no longer matches its metadata."""


@dataclass(frozen=True, slots=True)
class ArtifactMetadata:
    content_type: str
    etag: str | None = None
    last_modified: str | None = None
    content_length: int = 0
    content_sha256: str = ""


@dataclass(frozen=True, slots=True)
class ArtifactProjection:
    title: str | None
    cleaned_text: str | None
    status: str
    extractor: str | None
    diagnostics: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FetchArtifact:
    content: bytes
    metadata: ArtifactMetadata
    projection: ArtifactProjection


class FilesystemArtifactStore:
    def __init__(self, root: Path, *, max_content_bytes: int = 5_000_000) -> None:
        if max_content_bytes < 1:
            raise ValueError("artifact size limit must be positive")
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._root = root.resolve(strict=True)
        self._max_content_bytes = max_content_bytes

    def put(
        self,
        artifact_id: UUID,
        content: bytes,
        *,
        metadata: ArtifactMetadata,
        projection: ArtifactProjection,
    ) -> ArtifactMetadata:
        target = self._artifact_path(artifact_id)
        self._validate_input(content, metadata, projection)
        if target.exists():
            return self._existing_or_conflict(artifact_id, content, metadata, projection)

        stored_metadata = ArtifactMetadata(
            content_type=metadata.content_type,
            etag=metadata.etag,
            last_modified=metadata.last_modified,
            content_length=len(content),
            content_sha256=hashlib.sha256(content).hexdigest(),
        )
        temporary = Path(tempfile.mkdtemp(prefix=".tmp-", dir=self._root))
        try:
            self._write_durable(temporary / "content.html", content)
            metadata_bytes = json.dumps(
                asdict(stored_metadata),
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            self._write_durable(temporary / "metadata.json", metadata_bytes)
            projection_bytes = json.dumps(
                asdict(projection),
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            self._write_durable(temporary / "projection.json", projection_bytes)
            self._sync_directory(temporary)
            try:
                temporary.rename(target)
            except FileExistsError:
                return self._existing_or_conflict(artifact_id, content, metadata, projection)
            self._sync_directory(self._root)
            return stored_metadata
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)

    def read(self, artifact_id: UUID) -> FetchArtifact:
        target = self._artifact_path(artifact_id)
        if not target.is_dir() or target.is_symlink():
            raise ArtifactNotFoundError("fetch artifact was not found")
        content_path = target / "content.html"
        metadata_path = target / "metadata.json"
        projection_path = target / "projection.json"
        if content_path.is_symlink() or metadata_path.is_symlink() or projection_path.is_symlink():
            raise ArtifactIntegrityError("artifact files must not be symbolic links")
        try:
            metadata_bytes = metadata_path.read_bytes()
            if len(metadata_bytes) > _METADATA_LIMIT_BYTES:
                raise ArtifactIntegrityError("artifact metadata exceeds its size limit")
            metadata = self._parse_metadata(metadata_bytes)
            projection_bytes = projection_path.read_bytes()
            if len(projection_bytes) > _PROJECTION_LIMIT_BYTES:
                raise ArtifactIntegrityError("artifact projection exceeds its size limit")
            projection = self._parse_projection(projection_bytes)
            content = content_path.read_bytes()
        except FileNotFoundError as exc:
            raise ArtifactNotFoundError("fetch artifact is incomplete") from exc
        if len(content) > self._max_content_bytes:
            raise ArtifactIntegrityError("artifact content exceeds its size limit")
        if len(content) != metadata.content_length:
            raise ArtifactIntegrityError("artifact content length does not match metadata")
        if hashlib.sha256(content).hexdigest() != metadata.content_sha256:
            raise ArtifactIntegrityError("artifact content hash does not match metadata")
        return FetchArtifact(content, metadata, projection)

    def _artifact_path(self, artifact_id: UUID) -> Path:
        if not isinstance(artifact_id, UUID):
            raise InvalidArtifactIdError("artifact ID must be a UUID")
        return self._root / str(artifact_id)

    def _validate_input(
        self,
        content: bytes,
        metadata: ArtifactMetadata,
        projection: ArtifactProjection,
    ) -> None:
        if not isinstance(content, bytes) or not content:
            raise ValueError("artifact content must be non-empty bytes")
        if len(content) > self._max_content_bytes:
            raise ValueError("artifact content exceeds the size limit")
        if metadata.content_type not in _ALLOWED_CONTENT_TYPES:
            raise ValueError("artifact content type is not allowed")
        if metadata.etag is not None and (
            not isinstance(metadata.etag, str) or len(metadata.etag) > 512
        ):
            raise ValueError("artifact ETag is too long")
        if metadata.last_modified is not None and (
            not isinstance(metadata.last_modified, str) or len(metadata.last_modified) > 128
        ):
            raise ValueError("artifact Last-Modified is too long")
        self._validate_projection(projection)

    def _existing_or_conflict(
        self,
        artifact_id: UUID,
        content: bytes,
        requested: ArtifactMetadata,
        projection: ArtifactProjection,
    ) -> ArtifactMetadata:
        existing = self.read(artifact_id)
        matches = (
            existing.content == content
            and existing.metadata.content_type == requested.content_type
            and existing.metadata.etag == requested.etag
            and existing.metadata.last_modified == requested.last_modified
            and existing.projection == projection
        )
        if not matches:
            raise ArtifactConflictError("artifact ID already contains different evidence")
        return existing.metadata

    @staticmethod
    def _write_durable(path: Path, content: bytes) -> None:
        with path.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())

    @staticmethod
    def _sync_directory(path: Path) -> None:
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @staticmethod
    def _parse_metadata(payload: bytes) -> ArtifactMetadata:
        try:
            document: Any = json.loads(payload)
            if not isinstance(document, dict) or set(document) != {
                "content_type",
                "etag",
                "last_modified",
                "content_length",
                "content_sha256",
            }:
                raise ValueError
            metadata = ArtifactMetadata(**document)
        except (TypeError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
            raise ArtifactIntegrityError("artifact metadata is invalid") from exc
        if (
            metadata.content_type not in _ALLOWED_CONTENT_TYPES
            or not isinstance(metadata.content_length, int)
            or metadata.content_length < 1
            or not isinstance(metadata.content_sha256, str)
            or _SHA256_PATTERN.fullmatch(metadata.content_sha256) is None
            or (metadata.etag is not None and not isinstance(metadata.etag, str))
            or (metadata.last_modified is not None and not isinstance(metadata.last_modified, str))
        ):
            raise ArtifactIntegrityError("artifact metadata values are invalid")
        return metadata

    @staticmethod
    def _parse_projection(payload: bytes) -> ArtifactProjection:
        try:
            document: Any = json.loads(payload)
            if not isinstance(document, dict) or set(document) != {
                "title",
                "cleaned_text",
                "status",
                "extractor",
                "diagnostics",
            }:
                raise ValueError
            diagnostics = document["diagnostics"]
            if not isinstance(diagnostics, list) or not all(
                isinstance(item, str) for item in diagnostics
            ):
                raise ValueError
            document["diagnostics"] = tuple(diagnostics)
            projection = ArtifactProjection(**document)
            FilesystemArtifactStore._validate_projection(projection)
        except (TypeError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
            raise ArtifactIntegrityError("artifact projection is invalid") from exc
        return projection

    @staticmethod
    def _validate_projection(projection: ArtifactProjection) -> None:
        if not isinstance(projection.status, str) or projection.status not in {
            "SUCCESS",
            "PARTIAL",
            "FAILED",
        }:
            raise ValueError("artifact projection status is invalid")
        if projection.title is not None and (
            not isinstance(projection.title, str) or not 1 <= len(projection.title) <= 512
        ):
            raise ValueError("artifact projection title is invalid")
        if projection.cleaned_text is not None and (
            not isinstance(projection.cleaned_text, str)
            or not 1 <= len(projection.cleaned_text) <= 1_000_000
        ):
            raise ValueError("artifact projection text is invalid")
        if (
            not isinstance(projection.diagnostics, tuple)
            or len(projection.diagnostics) > 10
            or any(not item or len(item) > 200 for item in projection.diagnostics)
        ):
            raise ValueError("artifact projection diagnostics are invalid")
        if projection.extractor is not None and not isinstance(projection.extractor, str):
            raise ValueError("artifact projection extractor is invalid")
        if projection.status == "FAILED":
            if any(
                value is not None
                for value in (projection.title, projection.cleaned_text, projection.extractor)
            ):
                raise ValueError("failed artifact projection must not contain cleaned content")
            if not projection.diagnostics:
                raise ValueError("failed artifact projection requires diagnostics")
            return
        if (
            projection.title is None
            or projection.cleaned_text is None
            or projection.extractor not in {"TRAFILATURA", "BEAUTIFULSOUP"}
        ):
            raise ValueError("successful artifact projection is incomplete")
