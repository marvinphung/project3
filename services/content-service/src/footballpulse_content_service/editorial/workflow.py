from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from footballpulse_runtime_config import log_event

from footballpulse_content_service.editorial.repository import EditorialRevisionStore
from footballpulse_content_service.editorial.revision import EditorialRevision

LOGGER = logging.getLogger("footballpulse.content.editorial")


class EditorialWorkflow:
    """Application-level orchestration for optimistic editorial transitions."""

    def __init__(self, repository: EditorialRevisionStore) -> None:
        self._repository = repository

    def submit_for_review(
        self,
        generated_article_id: UUID,
        *,
        expected_revision_number: int,
        now: datetime,
    ) -> EditorialRevision:
        return self._update(
            generated_article_id,
            expected_revision_number,
            lambda current: current.submit_for_review(now),
        )

    def approve(
        self,
        generated_article_id: UUID,
        *,
        expected_revision_number: int,
        now: datetime,
    ) -> EditorialRevision:
        return self._update(
            generated_article_id,
            expected_revision_number,
            lambda current: current.approve(now),
        )

    def reject(
        self,
        generated_article_id: UUID,
        *,
        expected_revision_number: int,
        now: datetime,
    ) -> EditorialRevision:
        return self._update(
            generated_article_id,
            expected_revision_number,
            lambda current: current.reject(now),
        )

    def mark_stale(
        self,
        generated_article_id: UUID,
        *,
        expected_revision_number: int,
        story_version: int,
        now: datetime,
    ) -> EditorialRevision:
        return self._update(
            generated_article_id,
            expected_revision_number,
            lambda current: current.mark_stale(story_version=story_version, now=now),
        )

    def _update(
        self,
        generated_article_id: UUID,
        expected_revision_number: int,
        transition: Callable[[EditorialRevision], EditorialRevision],
    ) -> EditorialRevision:
        current = self._repository.get_current(generated_article_id)
        if current is None:
            raise ValueError("editorial revision does not exist")
        updated = transition(current)
        self._repository.update(updated, expected_revision_number=expected_revision_number)
        log_event(
            LOGGER,
            "editorial_revision_transitioned",
            generated_article_id=str(generated_article_id),
            previous_status=current.state.value,
            status=updated.state.value,
            revision_number=updated.revision_number,
        )
        return updated
