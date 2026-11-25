"""Store the episodes each show or anime download covers

Revision ID: download_episode_ids
Revises: movie_release_dates
Create Date: 2026-11-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "download_episode_ids"
down_revision: Union[str, None] = "movie_release_dates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("download_history", sa.Column("episode_ids", postgresql.ARRAY(sa.Integer()), nullable=True))
    op.create_index(
        "idx_download_history_episode_ids",
        "download_history",
        ["episode_ids"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("idx_download_history_episode_ids", table_name="download_history")
    op.drop_column("download_history", "episode_ids")
