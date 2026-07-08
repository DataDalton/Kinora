"""Make download_history.torrent_hash unique for upserts

Grabs across every path (interactive, RSS, wanted-search, music, manual) upsert
into download_history keyed on torrent_hash via ON CONFLICT, which requires a
unique index on that column. The initial schema created only a non-unique index.

Revision ID: download_history_hash_unique
Revises: download_gap_closers
Create Date: 2026-07-05

"""

from typing import Sequence, Union

from alembic import op

revision: str = "download_history_hash_unique"
down_revision: Union[str, None] = "download_gap_closers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Collapse any pre-existing duplicate rows, keeping the most recent per hash,
    # so the unique index can be created.
    op.execute("""
        DELETE FROM download_history a
        USING download_history b
        WHERE a.torrent_hash = b.torrent_hash
          AND a.id < b.id
        """)
    op.drop_index("idx_download_history_hash", table_name="download_history")
    op.create_index(
        "idx_download_history_hash",
        "download_history",
        ["torrent_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("idx_download_history_hash", table_name="download_history")
    op.create_index(
        "idx_download_history_hash",
        "download_history",
        ["torrent_hash"],
        unique=False,
    )
