"""media_profiles column realignment: drop generic quality columns, add min_seeds

Removes the non-namespaced quality columns that are shadowed by the per-type
(movie_/show_/anime_) columns and never read by the scorer, and adds a common
min_seeds threshold used by release scoring.

Revision ID: media_profiles_column_realign
Revises: download_history_hash_unique
Create Date: 2026-07-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# Revision identifiers, used by Alembic.
revision: str = "media_profiles_column_realign"
down_revision: Union[str, None] = "download_history_hash_unique"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Non-namespaced quality columns replaced by the per-type columns.
GENERIC_COLUMNS = [
    "resolutions",
    "codecs",
    "sources",
    "audio_codecs",
    "audio_channels",
    "hdr_formats",
    "editions",
    "min_size",
    "max_size",
]


def upgrade() -> None:
    for column in GENERIC_COLUMNS:
        op.drop_column("media_profiles", column)

    op.add_column(
        "media_profiles",
        sa.Column("min_seeds", sa.Integer(), server_default="1", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("media_profiles", "min_seeds")

    op.add_column("media_profiles", sa.Column("min_size", sa.Integer(), nullable=True))
    op.add_column("media_profiles", sa.Column("max_size", sa.Integer(), nullable=True))
    for column in ["resolutions", "codecs", "sources", "audio_codecs", "audio_channels", "hdr_formats", "editions"]:
        op.add_column(
            "media_profiles",
            sa.Column(column, sa.ARRAY(sa.Text()), server_default="{}", nullable=True),
        )
