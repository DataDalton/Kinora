"""Move profile uploader filters into the trusted list and replace the anime and music rule columns

Uploader names from profile uploader filters become Kinora trusted list entries, since the
safety template now decides which uploaders a profile accepts. Release groups and regex
patterns gain a mode. Existing lists keep their old behavior, so groups become required and
patterns must match. The anime subtitle and audio columns collapse into anime_allow_hardsub
and anime_audio_preference. The music cutoff column goes, because upgrades now stop at the
highest allowed tier.

Revision ID: profile_release_rules
Revises: download_episode_ids
Create Date: 2026-11-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

revision: str = "profile_release_rules"
down_revision: Union[str, None] = "download_episode_ids"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Each distinct uploader name joins the trusted list unless an entry already uses it.
    op.execute("""
        INSERT INTO trusted_uploaders (display_name, ext_name, leetx_name, is_default, enabled)
        SELECT DISTINCT ON (lower(name)) name, name, name, false, true
        FROM (
            SELECT trim(unnest(uploaders)) AS name FROM media_profiles
        ) names
        WHERE name <> ''
          AND NOT EXISTS (
              SELECT 1 FROM trusted_uploaders t
              WHERE lower(t.display_name) = lower(names.name)
                 OR lower(t.ext_name) = lower(names.name)
                 OR lower(t.leetx_name) = lower(names.name)
          )
        ORDER BY lower(name), name
        """)
    op.drop_column("media_profiles", "uploaders")

    op.add_column(
        "media_profiles",
        sa.Column("release_group_mode", sa.String(length=10), server_default="prefer", nullable=False),
    )
    op.add_column(
        "media_profiles",
        sa.Column("regex_mode", sa.String(length=10), server_default="exclude", nullable=False),
    )
    op.execute("UPDATE media_profiles SET release_group_mode = 'require' WHERE cardinality(release_groups) > 0")
    op.execute("UPDATE media_profiles SET regex_mode = 'include' WHERE cardinality(regex_filters) > 0")

    op.add_column(
        "media_profiles",
        sa.Column("anime_audio_preference", sa.String(length=20), server_default="any", nullable=False),
    )
    op.execute("UPDATE media_profiles SET anime_audio_preference = 'dual_only' WHERE anime_prefer_dual_audio")
    # A profile that picked hardsub as its subtitle type wanted hardsubs accepted.
    op.execute("UPDATE media_profiles SET anime_allow_hardsub = true WHERE anime_subtitle_preference = 'hardsub'")
    op.drop_column("media_profiles", "anime_prefer_dual_audio")
    op.drop_column("media_profiles", "anime_subtitle_preference")

    op.drop_column("media_profiles", "music_quality_cutoff")


def downgrade() -> None:
    op.add_column(
        "media_profiles",
        sa.Column("music_quality_cutoff", sa.String(length=50), server_default="lossless_16_44", nullable=True),
    )

    op.add_column(
        "media_profiles",
        sa.Column("anime_subtitle_preference", sa.String(length=20), server_default="softsub", nullable=True),
    )
    op.add_column("media_profiles", sa.Column("anime_prefer_dual_audio", sa.Boolean(), nullable=True))
    op.execute("UPDATE media_profiles SET anime_prefer_dual_audio = (anime_audio_preference = 'dual_only')")
    op.drop_column("media_profiles", "anime_audio_preference")

    op.drop_column("media_profiles", "regex_mode")
    op.drop_column("media_profiles", "release_group_mode")

    # Trusted list entries added by the upgrade stay, since they cannot be told apart.
    op.add_column("media_profiles", sa.Column("uploaders", ARRAY(sa.Text()), server_default="{}", nullable=True))
