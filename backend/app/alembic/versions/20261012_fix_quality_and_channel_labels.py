"""relabel stored video quality by width and drop FFmpeg channel layout suffixes

Video quality used to come from the frame height alone, so a letterboxed 4K film such as
3840x1600 was stored as 1080p. It is now the larger of the height and the height the
width implies at 16:9, matching metadata_extractor.qualityFromDimensions. Channel layouts
such as 5.1(side) lose the speaker suffix, matching media_files._audio_channels.

Only rows whose quality is a video label (digits then p) are relabeled, so music quality
labels are untouched. Items whose detected quality came from a relabeled file follow it.

Revision ID: fix_quality_and_channel_labels
Revises: add_user_preferences
Create Date: 2026-10-12
"""

from typing import Sequence, Union

from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "fix_quality_and_channel_labels"
down_revision: Union[str, None] = "add_user_preferences"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ITEM_TABLES = ("movies", "episodes", "anime_episodes")


def upgrade() -> None:
    op.execute("""
        WITH dims AS (
            SELECT id,
                   split_part(resolution, 'x', 2)::int AS height,
                   GREATEST(
                       split_part(resolution, 'x', 2)::int,
                       split_part(resolution, 'x', 1)::int * 9 / 16
                   ) AS nominal_height
            FROM media_files
            WHERE resolution ~ '^[0-9]+x[0-9]+$' AND quality ~ '^[0-9]+p$'
        )
        UPDATE media_files mf
        SET quality = CASE
            WHEN dims.nominal_height >= 2000 THEN '2160p'
            WHEN dims.nominal_height >= 1000 THEN '1080p'
            WHEN dims.nominal_height >= 700 THEN '720p'
            WHEN dims.nominal_height >= 460 THEN '480p'
            ELSE dims.height || 'p'
        END
        FROM dims
        WHERE mf.id = dims.id
        """)

    op.execute("""
        UPDATE media_files
        SET audio_channels = regexp_replace(audio_channels, '\\(.*\\)$', '')
        WHERE audio_channels ~ '\\(.*\\)$'
        """)

    for table in ITEM_TABLES:
        op.execute(f"""
            UPDATE {table} item
            SET quality_detected = mf.quality
            FROM media_files mf
            WHERE mf.file_path = item.file_path
              AND item.quality_detected ~ '^[0-9]+p$'
              AND mf.quality ~ '^[0-9]+p$'
              AND item.quality_detected IS DISTINCT FROM mf.quality
            """)


def downgrade() -> None:
    # The original height-only labels and FFmpeg suffixes are not recoverable from the
    # stored values, and the corrected labels are valid under the old code as well.
    pass
