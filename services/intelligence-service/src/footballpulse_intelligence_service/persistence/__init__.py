"""Persistence adapters owned by intelligence-service."""

from footballpulse_intelligence_service.persistence.postgres_repository import (
    PostgresEntityCatalogRepository,
    PostgresUnresolvedMentionRepository,
)

__all__ = ["PostgresEntityCatalogRepository", "PostgresUnresolvedMentionRepository"]
