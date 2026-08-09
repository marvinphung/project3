class EntityCatalogError(Exception):
    """Base error for canonical entity catalog operations."""


class EntityNotFoundError(EntityCatalogError):
    """Raised when an entity does not exist."""


class AliasNotFoundError(EntityCatalogError):
    """Raised when an alias does not exist."""


class EntityConflictError(EntityCatalogError):
    """Raised for uniqueness or optimistic concurrency conflicts."""
