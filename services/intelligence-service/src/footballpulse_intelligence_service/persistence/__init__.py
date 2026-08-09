"""Persistence adapters owned by intelligence-service."""

from footballpulse_intelligence_service.persistence.postgres_repository import (
    PostgresEmbeddingRepository,
    PostgresEntityCatalogRepository,
    PostgresUnresolvedMentionRepository,
)

__all__ = [
    "PostgresEmbeddingRepository",
    "PostgresEntityCatalogRepository",
    "PostgresUnresolvedMentionRepository",
]
