"""Search backoff tracking

Adds last_search_at and search_attempts to the searchable media tables so the
automated searches can back off items that keep coming up empty instead of
re-searching every one of them every cycle. The RSS monitor has no backoff and
catches late-appearing releases within one feed cycle regardless.

Revision ID: search_backoff
Revises: release_index
Create Date: 2026-07-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# Revision identifiers, used by Alembic.
revision: str = "search_backoff"
down_revision: Union[str, None] = "release_index"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ["movies", "shows", "anime", "albums"]


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column("last_search_at", sa.TIMESTAMP(), nullable=True))
        op.add_column(
            table,
            sa.Column("search_attempts", sa.Integer(), server_default="0", nullable=False),
        )
        op.create_index(f"idx_{table}_last_search_at", table, ["last_search_at"])


def downgrade() -> None:
    for table in TABLES:
        op.drop_index(f"idx_{table}_last_search_at", table_name=table)
        op.drop_column(table, "search_attempts")
        op.drop_column(table, "last_search_at")
