"""Trigram indexes for library search

Enables pg_trgm and adds GIN trigram indexes on the title/name columns queried by
library search, so ILIKE '%term%' lookups use an index instead of scanning every
table on each keystroke.

Revision ID: search_trgm_indexes
Revises: media_files
Create Date: 2026-07-26
"""

from typing import Sequence, Union

from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "search_trgm_indexes"
down_revision: Union[str, None] = "media_files"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (index name, table, column) for every column library search matches against.
TRGM_INDEXES = [
    ("idx_movies_title_trgm", "movies", "title"),
    ("idx_shows_title_trgm", "shows", "title"),
    ("idx_anime_title_trgm", "anime", "title"),
    ("idx_artists_name_trgm", "artists", "name"),
    ("idx_albums_title_trgm", "albums", "title"),
]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    for indexName, table, column in TRGM_INDEXES:
        op.execute(f"CREATE INDEX IF NOT EXISTS {indexName} ON {table} " f"USING gin ({column} gin_trgm_ops)")


def downgrade() -> None:
    for indexName, _table, _column in TRGM_INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {indexName}")
