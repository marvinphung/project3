from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from uuid import UUID

from footballpulse_content_service.editorial.publication import PublicationService
from footballpulse_content_service.editorial.repository import EditorialRevisionStore
from footballpulse_content_service.editorial.revision import EditorialRevision
from footballpulse_content_service.editorial.workflow import EditorialWorkflow

from footballpulse_api_gateway.api.editorial_admin import EditorialRevisionDetailView, EditorialRevisionView, PublicationView


class ContentEditorialAdminAdapter:
    """Adapts content-service editorial use cases to the gateway API contract."""

    def __init__(
        self,
        *,
        revision_repository: EditorialRevisionStore,
        publication_service: PublicationService,
    ) -> None:
        self._revision_repository = revision_repository
        self._workflow = EditorialWorkflow(revision_repository)
        self._publication_service = publication_service

    def submit_for_review(
        self, article_id: UUID, *, expected_revision_number: int, now: datetime
    ) -> EditorialRevisionView:
        return self._revision_view(
            self._workflow.submit_for_review(
                article_id, expected_revision_number=expected_revision_number, now=now
            )
        )

    def list_revisions_page(
        self, *, limit: int, offset: int, state: str | None
    ) -> tuple[list[EditorialRevisionDetailView], int]:
        revisions = self._revision_repository.list_current(limit=500)
        if state is not None:
            revisions = [revision for revision in revisions if revision.state.value == state]
        total = len(revisions)
        return [self._detail_view(item) for item in revisions[offset:offset + limit]], total

    def get_revision(self, article_id: UUID) -> EditorialRevisionDetailView:
        revision = self._revision_repository.get_current(article_id)
        if revision is None:
            raise ValueError("editorial revision does not exist")
        return self._detail_view(revision)

    def update_content(
        self, article_id: UUID, *, expected_revision_number: int, title_vi: str, body_vi: str, now: datetime
    ) -> EditorialRevisionDetailView:
        current = self._revision_repository.get_current(article_id)
        if current is None:
            raise ValueError("editorial revision does not exist")
        if current.state.value not in {"DRAFT", "REJECTED"}:
            raise ValueError("only DRAFT or REJECTED revision can be edited")
        updated = replace(current, title_vi=title_vi, body_vi=body_vi, updated_at=now)
        self._revision_repository.update(updated, expected_revision_number=expected_revision_number)
        return self._detail_view(updated)

    def approve(
        self, article_id: UUID, *, expected_revision_number: int, now: datetime
    ) -> EditorialRevisionView:
        return self._revision_view(
            self._workflow.approve(
                article_id, expected_revision_number=expected_revision_number, now=now
            )
        )

    def reject(
        self, article_id: UUID, *, expected_revision_number: int, now: datetime
    ) -> EditorialRevisionView:
        return self._revision_view(
            self._workflow.reject(
                article_id, expected_revision_number=expected_revision_number, now=now
            )
        )

    def publish(
        self, article_id: UUID, *, slug: str, idempotency_key: str, now: datetime
    ) -> PublicationView:
        revision = self._revision_repository.get_current(article_id)
        if revision is None:
            raise ValueError("editorial revision does not exist")
        publication = self._publication_service.publish(
            revision=revision,
            slug=slug,
            idempotency_key=idempotency_key,
            published_at=now,
        )
        return PublicationView(
            id=publication.id,
            generated_article_id=publication.generated_article_id,
            revision_id=publication.revision_id,
            story_id=publication.story_id,
            story_version=publication.story_version,
            slug=publication.slug,
            title_vi=publication.title_vi,
            body_vi=publication.body_vi,
            published_at=publication.published_at,
        )

    @staticmethod
    def _revision_view(revision: EditorialRevision) -> EditorialRevisionView:
        return EditorialRevisionView(
            generated_article_id=revision.generated_article_id,
            revision_id=revision.id,
            revision_number=revision.revision_number,
            story_version=revision.story_version,
            state=revision.state.value,
            updated_at=revision.updated_at,
        )

    @staticmethod
    def _detail_view(revision: EditorialRevision) -> EditorialRevisionDetailView:
        return EditorialRevisionDetailView(
            generated_article_id=revision.generated_article_id,
            revision_id=revision.id,
            revision_number=revision.revision_number,
            story_version=revision.story_version,
            state=revision.state.value,
            updated_at=revision.updated_at,
            story_id=revision.story_id,
            title_en=revision.title_en,
            body_en=revision.body_en,
            title_vi=revision.title_vi,
            body_vi=revision.body_vi,
        )
