"""
Database module with connection pooling, repositories, and SQLAlchemy Core models.
"""
from app.db.connection import get_pool, get_db, close_pool, init_pool
from app.db.exceptions import NotFoundError, DuplicateError

__all__ = [
    "get_pool",
    "get_db",
    "close_pool",
    "init_pool",
    "NotFoundError",
    "DuplicateError",
]
