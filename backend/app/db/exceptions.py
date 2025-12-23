"""
Database exception types for consistent error handling.
"""
import asyncpg


class NotFoundError(Exception):
    """Raised when a requested resource is not found in the database."""

    pass


class DuplicateError(Exception):
    """Raised when attempting to create a duplicate record."""

    pass


def handleDbError(e: Exception) -> None:
    """Convert asyncpg exceptions to application-specific exceptions."""
    if isinstance(e, asyncpg.UniqueViolationError):
        raise DuplicateError(str(e))
    raise
