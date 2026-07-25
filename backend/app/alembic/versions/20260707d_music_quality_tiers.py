"""music quality tiers on media_profiles

Replace the flat music_preferred_quality list with an ordered music_quality_tiers
allowed set and a music_quality_cutoff. Existing profiles are backfilled from the
old list.

Revision ID: music_quality_tiers
Revises: seed_upgrade_interval
Create Date: 2026-07-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Revision identifiers, used by Alembic.
revision: str = "music_quality_tiers"
down_revision: Union[str, None] = "seed_upgrade_interval"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# All lossless rungs, highest quality first.
_ALL_LOSSLESS = [
    "lossless_24_192",
    "lossless_24_96",
    "lossless_24_48",
    "lossless_24_unknown",
    "lossless_16_48",
    "lossless_16_44",
    "lossless_unknown",
]
# Lossy rungs from lowest to highest quality.
_LOSSY_ASCENDING = ["ogg", "aac", "mp3_128", "mp3_192", "mp3_256", "mp3_320"]
_DEFAULT_TIERS = _ALL_LOSSLESS + ["mp3_320", "mp3_256"]


def _map_tiers(old):
    """Map an old music_preferred_quality list to (tiers, cutoff)."""
    has_flac = False
    lossy = []
    for value in old or []:
        token = (value or "").lower()
        if token == "flac":
            has_flac = True
        elif token in _LOSSY_ASCENDING:
            lossy.append(token)

    tiers = []
    if has_flac:
        tiers.extend(_ALL_LOSSLESS)
    for tier in reversed(_LOSSY_ASCENDING):
        if tier in lossy and tier not in tiers:
            tiers.append(tier)
    if not tiers:
        tiers = list(_DEFAULT_TIERS)

    if has_flac:
        cutoff = "lossless_16_44"
    else:
        cutoff = next((tier for tier in reversed(_LOSSY_ASCENDING) if tier in lossy), tiers[-1])
    return tiers, cutoff


def upgrade() -> None:
    op.add_column("media_profiles", sa.Column("music_quality_tiers", postgresql.ARRAY(sa.Text()), nullable=True))
    op.add_column("media_profiles", sa.Column("music_quality_cutoff", sa.String(length=50), nullable=True))

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, music_preferred_quality FROM media_profiles")).fetchall()
    update = sa.text(
        "UPDATE media_profiles SET music_quality_tiers = :tiers, music_quality_cutoff = :cutoff WHERE id = :id"
    ).bindparams(sa.bindparam("tiers", type_=postgresql.ARRAY(sa.Text())))
    for row in rows:
        tiers, cutoff = _map_tiers(row[1])
        conn.execute(update, {"tiers": tiers, "cutoff": cutoff, "id": row[0]})

    op.alter_column(
        "media_profiles",
        "music_quality_tiers",
        server_default=sa.text("'{" + ",".join(_DEFAULT_TIERS) + "}'"),
    )
    op.alter_column("media_profiles", "music_quality_cutoff", server_default="lossless_16_44")

    op.drop_column("media_profiles", "music_preferred_quality")


def downgrade() -> None:
    op.add_column(
        "media_profiles",
        sa.Column(
            "music_preferred_quality",
            postgresql.ARRAY(sa.Text()),
            server_default="{'flac','mp3_320','mp3_256','aac'}",
            nullable=True,
        ),
    )
    op.drop_column("media_profiles", "music_quality_cutoff")
    op.drop_column("media_profiles", "music_quality_tiers")
