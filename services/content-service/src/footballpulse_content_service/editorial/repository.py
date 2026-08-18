from __future__ import annotations

from typing import Protocol
from uuid import UUID

from footballpulse_content_service.editorial.revision import EditorialRevision


class RevisionConflictError(RuntimeError):
    """The revision changed since the caller loaded it."""


class EditorialRevisionStore(Protocol):
    def get_current(self, generated_article_id: UUID) -> EditorialRevision | None: ...

    def list_current(self, *, limit: int = 100) -> list[EditorialRevision]: ...

    def update(self, revision: EditorialRevision, *, expected_revision_number: int) -> None: ...


class EditorialRevisionRepository:
    """Small repository contract implementation used by the local workflow."""

    def __init__(self) -> None:
        self._current: dict[UUID, EditorialRevision] = {}

    def add(self, revision: EditorialRevision) -> None:
        current = self._current.get(revision.generated_article_id)
        if current is not None and revision.revision_number <= current.revision_number:
            raise RevisionConflictError("revision number is not newer than current revision")
        self._current[revision.generated_article_id] = revision

    def get_current(self, generated_article_id: UUID) -> EditorialRevision | None:
        return self._current.get(generated_article_id)

    def update(self, revision: EditorialRevision, *, expected_revision_number: int) -> None:
        current = self._current.get(revision.generated_article_id)
        if (
            current is None
            or current.id != revision.id
            or current.revision_number != expected_revision_number
        ):
            raise RevisionConflictError("expected revision is no longer current")
        self._current[revision.generated_article_id] = revision
