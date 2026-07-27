"""Local release index

One row per torrent release ever seen by any search, RSS pull, or catalog sync,
with the parsed quality attributes and seed counts. Searches read this table first
and only go to the indexers for what it cannot answer, so the index grows passively
from normal operation.

Revision ID: release_index
Revises: search_trgm_indexes
Create Date: 2026-07-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# Revision identifiers, used by Alembic.
revision: str = "release_index"
down_revision: Union[str, None] = "search_trgm_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "releases",
        sa.Column("id", sa.Integer(), primary_key=True),
        # Stable identity: the info hash when known, otherwise a digest of the
        # indexer plus detail URL or title. Upserts key on this.
        sa.Column("dedupe_key", sa.String(length=64), nullable=False),
        sa.Column("info_hash", sa.String(length=64)),
        sa.Column("title", sa.String(length=1000), nullable=False),
        # Lowercased, punctuation-stripped title used for local matching.
        sa.Column("normalized_title", sa.String(length=1000), nullable=False),
        sa.Column("indexer", sa.String(length=50), nullable=False),
        sa.Column("category", sa.String(length=50)),
        sa.Column("detail_url", sa.String(length=2000)),
        sa.Column("magnet_link", sa.Text()),
        sa.Column("torrent_url", sa.String(length=2000)),
        sa.Column("size", sa.BigInteger()),
        sa.Column("size_string", sa.String(length=50)),
        sa.Column("seeders", sa.Integer(), server_default="0", nullable=False),
        sa.Column("leechers", sa.Integer(), server_default="0", nullable=False),
        sa.Column("upload_date", sa.TIMESTAMP()),
        sa.Column("uploader", sa.String(length=255)),
        # Parsed video quality attributes
        sa.Column("quality", sa.String(length=20)),
        sa.Column("codec", sa.String(length=20)),
        sa.Column("source", sa.String(length=30)),
        sa.Column("audio", sa.String(length=50)),
        sa.Column("audio_channels", sa.String(length=20)),
        sa.Column("hdr", sa.String(length=30)),
        sa.Column("edition", sa.String(length=50)),
        sa.Column("language", sa.String(length=10)),
        sa.Column("release_group", sa.String(length=100)),
        sa.Column("is_proper", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_repack", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        # Parsed music quality attributes
        sa.Column("audio_format", sa.String(length=20)),
        sa.Column("audio_bitrate", sa.String(length=10)),
        sa.Column("bit_depth", sa.Integer()),
        sa.Column("sample_rate", sa.Integer()),
        sa.Column("quality_tier", sa.String(length=30)),
        sa.Column("is_lossless", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_discography", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("artist", sa.String(length=500)),
        sa.Column("album", sa.String(length=500)),
        sa.Column("year", sa.Integer()),
        sa.Column("first_seen_at", sa.TIMESTAMP(), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("last_seen_at", sa.TIMESTAMP(), server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("dedupe_key", name="uq_releases_dedupe_key"),
    )

    op.create_index("idx_releases_info_hash", "releases", ["info_hash"])
    op.create_index("idx_releases_indexer", "releases", ["indexer"])
    op.create_index("idx_releases_category", "releases", ["category"])
    op.create_index("idx_releases_quality", "releases", ["quality"])
    op.create_index("idx_releases_last_seen", "releases", ["last_seen_at"])
    op.create_index("idx_releases_seeders", "releases", ["seeders"])
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_releases_normalized_title_trgm "
        "ON releases USING gin (normalized_title gin_trgm_ops)"
    )


def downgrade() -> None:
    op.drop_table("releases")
