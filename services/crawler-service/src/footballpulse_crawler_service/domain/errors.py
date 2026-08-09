class DomainError(Exception):
    """Base error for expected crawler domain failures."""


class DomainValidationError(DomainError, ValueError):
    """Raised when a command violates a crawler domain invariant."""


class SourceNotFoundError(DomainError):
    """Raised when the requested source does not exist."""


class SourceConflictError(DomainError):
    """Raised when source identity or expected version conflicts."""
