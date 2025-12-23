"""add anime series_id for grouping related seasons

Revision ID: add_anime_series_id
Revises: c576e9cecf58
Create Date: 2025-12-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# Revision identifiers, used by Alembic.
revision: str = 'add_anime_series_id'
down_revision: Union[str, None] = 'c576e9cecf58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add series_id column to group related anime (sequels/prequels) together
    # series_id points to the "primary" anime entry in the series
    op.add_column('anime', sa.Column('series_id', sa.Integer(), nullable=True))
    op.add_column('anime', sa.Column('season_order', sa.Integer(), nullable=True))
    op.create_index('idx_anime_series_id', 'anime', ['series_id'], unique=False)

    # Self-referencing foreign key (series_id points to another anime.id)
    op.create_foreign_key(
        'fk_anime_series_id_anime',
        'anime', 'anime',
        ['series_id'], ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    op.drop_constraint('fk_anime_series_id_anime', 'anime', type_='foreignkey')
    op.drop_index('idx_anime_series_id', table_name='anime')
    op.drop_column('anime', 'season_order')
    op.drop_column('anime', 'series_id')
