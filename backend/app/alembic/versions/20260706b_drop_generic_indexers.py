"""drop the generic indexers column from media_profiles

The non-namespaced `indexers` column is shadowed by the per-type
movie_indexers/show_indexers/anime_indexers/music_indexers columns. It is never
read by indexer selection (get_indexers_for_type uses only the per-type columns)
and is never sent by the frontend. This removes the dead column.

Revision ID: drop_generic_indexers
Revises: media_profiles_column_realign
Create Date: 2026-07-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# Revision identifiers, used by Alembic.
revision: str = "drop_generic_indexers"
down_revision: Union[str, None] = "media_profiles_column_realign"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("media_profiles", "indexers")


def downgrade() -> None:
    op.add_column(
        "media_profiles",
        sa.Column("indexers", sa.ARRAY(sa.Text()), server_default="{}", nullable=True),
    )
