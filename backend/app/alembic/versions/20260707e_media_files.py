"""media_files table for persisted per-file metadata

One row per physical media file with its ffprobe attributes, so the file panel reads
from the database instead of probing on every load, and multiple versions of a movie
are each represented.

Revision ID: media_files
Revises: music_quality_tiers
Create Date: 2026-07-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# Revision identifiers, used by Alembic.
revision: str = "media_files"
down_revision: Union[str, None] = "music_quality_tiers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "media_files",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("media_type", sa.String(length=20), nullable=False),
        sa.Column("media_id", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(length=1000), nullable=False),
        sa.Column("file_name", sa.String(length=500)),
        sa.Column("file_size", sa.BigInteger()),
        sa.Column("quality", sa.String(length=100)),
        sa.Column("resolution", sa.String(length=50)),
        sa.Column("codec", sa.String(length=50)),
        sa.Column("audio_codec", sa.String(length=50)),
        sa.Column("audio_channels", sa.String(length=50)),
        sa.Column("container", sa.String(length=20)),
        sa.Column("bit_depth", sa.String(length=20)),
        sa.Column("hdr", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("file_path", name="media_files_file_path_unique"),
    )
    op.create_index("idx_media_files_media", "media_files", ["media_type", "media_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_media_files_media", table_name="media_files")
    op.drop_table("media_files")
