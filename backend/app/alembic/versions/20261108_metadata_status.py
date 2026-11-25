"""Metadata status column

Adds metadata_status to movies, shows and anime for the status the metadata provider
reports (TMDB's Released or Returning Series, AniList's RELEASING or FINISHED). The
status column keeps Kinora's own state (wanted, downloading, processing, completed).

The metadata refresh used to write the provider's status into the status column. Rows
holding a provider value move it to metadata_status and get their Kinora state back,
worked out from their files and active downloads.

Revision ID: metadata_status
Revises: episode_search_backoff
Create Date: 2026-11-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# Revision identifiers, used by Alembic.
revision: str = "metadata_status"
down_revision: Union[str, None] = "episode_search_backoff"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

KINORA_STATUSES = "('wanted', 'downloading', 'processing', 'completed')"

# Per table, the media type in download_history and the SQL deciding whether it has a file.
TABLES = {
    "movies": ("movie", "t.has_file"),
    "shows": ("show", "EXISTS (SELECT 1 FROM episodes e WHERE e.show_id = t.id AND e.has_file)"),
    "anime": (
        "anime",
        "(t.has_file OR EXISTS (SELECT 1 FROM anime_episodes ae WHERE ae.anime_id = t.id AND ae.has_file))",
    ),
}


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table, (mediaType, hasFileSql) in TABLES.items():
        columns = {c["name"] for c in inspector.get_columns(table)}
        if "metadata_status" not in columns:
            op.add_column(table, sa.Column("metadata_status", sa.String(50), nullable=True))
        op.execute(f"""
            UPDATE {table} t SET
                metadata_status = t.status,
                status = CASE
                    WHEN EXISTS (
                        SELECT 1 FROM download_history dh
                        WHERE dh.media_type = '{mediaType}' AND dh.media_id = t.id
                          AND dh.status IN ('downloading', 'pending', 'processing')
                    ) THEN 'downloading'
                    WHEN {hasFileSql} THEN 'completed'
                    ELSE 'wanted'
                END
            WHERE t.status NOT IN {KINORA_STATUSES}
            """)


def downgrade() -> None:
    for table in TABLES:
        op.drop_column(table, "metadata_status")
