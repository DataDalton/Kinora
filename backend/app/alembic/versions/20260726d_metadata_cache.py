"""Persistent metadata cache

Postgres-backed second tier under the Dragonfly metadata cache. Fetched TMDB,
Anilist, and Deezer payloads survive container restarts, and each row carries its
own TTL so old, unchanging records stay valid far longer than in-production ones.
Stale rows also serve as a fallback when a provider is unreachable.

Revision ID: metadata_cache
Revises: search_backoff
Create Date: 2026-07-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Revision identifiers, used by Alembic.
revision: str = "metadata_cache"
down_revision: Union[str, None] = "search_backoff"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "metadata_cache",
        sa.Column("cache_key", sa.Text(), primary_key=True),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("ttl_seconds", sa.Integer(), nullable=False),
        sa.Column("fetched_at", sa.TIMESTAMP(), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("idx_metadata_cache_provider", "metadata_cache", ["provider"])
    op.create_index("idx_metadata_cache_fetched_at", "metadata_cache", ["fetched_at"])


def downgrade() -> None:
    op.drop_table("metadata_cache")
