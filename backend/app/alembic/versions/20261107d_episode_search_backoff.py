"""Episode search backoff

Adds last_search_at and search_attempts to episodes and anime_episodes, so the upgrade
search can search one episode at a time and back off episodes that keep coming up empty,
the same way it does for movies and albums.

Revision ID: episode_search_backoff
Revises: safety_templates
Create Date: 2026-11-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# Revision identifiers, used by Alembic.
revision: str = "episode_search_backoff"
down_revision: Union[str, None] = "safety_templates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ["episodes", "anime_episodes"]


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table in TABLES:
        columns = {c["name"] for c in inspector.get_columns(table)}
        if "last_search_at" not in columns:
            op.add_column(table, sa.Column("last_search_at", sa.TIMESTAMP(), nullable=True))
            op.create_index(f"idx_{table}_last_search_at", table, ["last_search_at"])
        if "search_attempts" not in columns:
            op.add_column(
                table,
                sa.Column("search_attempts", sa.Integer(), server_default="0", nullable=False),
            )


def downgrade() -> None:
    for table in TABLES:
        op.drop_index(f"idx_{table}_last_search_at", table_name=table)
        op.drop_column(table, "search_attempts")
        op.drop_column(table, "last_search_at")
