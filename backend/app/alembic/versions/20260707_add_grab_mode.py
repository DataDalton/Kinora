"""add grab_mode to download_history (auto/manual/upgrade)

Revision ID: add_grab_mode
Revises: seed_opensubtitles_setting
Create Date: 2026-07-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# Revision identifiers, used by Alembic.
revision: str = "add_grab_mode"
down_revision: Union[str, None] = "seed_opensubtitles_setting"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "download_history",
        sa.Column("grab_mode", sa.String(length=20), server_default="auto", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("download_history", "grab_mode")
