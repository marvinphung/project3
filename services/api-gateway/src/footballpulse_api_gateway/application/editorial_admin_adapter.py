from __future__ import annotations

from datetime import datetime
from uuid import UUID

from footballpulse_content_service.editorial.publication import PublicationService
from footballpulse_content_service.editorial.repository import EditorialRevisionStore
from footballpulse_content_service.editorial.revision import EditorialRevision
from footballpulse_content_service.editorial.workflow import EditorialWorkflow

from footballpulse_api_gateway.api.editorial_admin import EditorialRevisionView, PublicationView


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
