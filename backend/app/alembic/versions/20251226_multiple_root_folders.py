"""add multiple root folders support

Revision ID: multiple_root_folders
Revises: add_validation_mode
Create Date: 2025-12-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'multiple_root_folders'
down_revision: Union[str, None] = 'add_validation_mode'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create root_folders table
    op.create_table(
        'root_folders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('media_type', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('root_path', sa.String(length=500), nullable=False),
        sa.Column('download_path', sa.String(length=500), nullable=False),
        sa.Column('priority', sa.Integer(), server_default='0', nullable=False),
        sa.Column('fill_threshold_percent', sa.Integer(), nullable=True),
        sa.Column('fill_threshold_gb', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('is_default', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('total_space_bytes', sa.BigInteger(), nullable=True),
        sa.Column('free_space_bytes', sa.BigInteger(), nullable=True),
        sa.Column('last_health_check', sa.DateTime(), nullable=True),
        sa.Column('health_status', sa.String(length=20), server_default='unknown', nullable=False),
        sa.Column('health_message', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('media_type', 'root_path', name='uq_root_folders_media_type_root_path')
    )
    op.create_index('idx_root_folders_media_type', 'root_folders', ['media_type'], unique=False)

    # Create folder_selection_settings table
    op.create_table(
        'folder_selection_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('media_type', sa.String(length=20), nullable=False),
        sa.Column('selection_mode', sa.String(length=20), server_default='most_free_space', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('media_type', name='uq_folder_selection_settings_media_type')
    )

    # Add root_folder_id to movies
    op.add_column('movies', sa.Column('root_folder_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_movies_root_folder_id', 'movies', 'root_folders', ['root_folder_id'], ['id'], ondelete='SET NULL')
    op.drop_column('movies', 'root_folder_path')

    # Add root_folder_id to shows
    op.add_column('shows', sa.Column('root_folder_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_shows_root_folder_id', 'shows', 'root_folders', ['root_folder_id'], ['id'], ondelete='SET NULL')
    op.drop_column('shows', 'root_folder_path')

    # Add root_folder_id to anime
    op.add_column('anime', sa.Column('root_folder_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_anime_root_folder_id', 'anime', 'root_folders', ['root_folder_id'], ['id'], ondelete='SET NULL')
    op.drop_column('anime', 'root_folder_path')

    # Add root_folder_id to artists
    op.add_column('artists', sa.Column('root_folder_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_artists_root_folder_id', 'artists', 'root_folders', ['root_folder_id'], ['id'], ondelete='SET NULL')
    op.drop_column('artists', 'root_folder_path')

    # Add root_folder_id to albums
    op.add_column('albums', sa.Column('root_folder_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_albums_root_folder_id', 'albums', 'root_folders', ['root_folder_id'], ['id'], ondelete='SET NULL')
    op.drop_column('albums', 'root_folder_path')

    # Add root_folder_id to download_history
    op.add_column('download_history', sa.Column('root_folder_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_download_history_root_folder_id', 'download_history', 'root_folders', ['root_folder_id'], ['id'], ondelete='SET NULL')

    # Delete old root folder settings from app_settings
    op.execute("DELETE FROM app_settings WHERE key IN ('root_folder_movies', 'root_folder_shows', 'root_folder_anime', 'root_folder_music')")


def downgrade() -> None:
    # Remove root_folder_id from download_history
    op.drop_constraint('fk_download_history_root_folder_id', 'download_history', type_='foreignkey')
    op.drop_column('download_history', 'root_folder_id')

    # Restore root_folder_path and remove root_folder_id from albums
    op.add_column('albums', sa.Column('root_folder_path', sa.String(length=500), nullable=True))
    op.drop_constraint('fk_albums_root_folder_id', 'albums', type_='foreignkey')
    op.drop_column('albums', 'root_folder_id')

    # Restore root_folder_path and remove root_folder_id from artists
    op.add_column('artists', sa.Column('root_folder_path', sa.String(length=500), nullable=True))
    op.drop_constraint('fk_artists_root_folder_id', 'artists', type_='foreignkey')
    op.drop_column('artists', 'root_folder_id')

    # Restore root_folder_path and remove root_folder_id from anime
    op.add_column('anime', sa.Column('root_folder_path', sa.String(length=500), nullable=True))
    op.drop_constraint('fk_anime_root_folder_id', 'anime', type_='foreignkey')
    op.drop_column('anime', 'root_folder_id')

    # Restore root_folder_path and remove root_folder_id from shows
    op.add_column('shows', sa.Column('root_folder_path', sa.String(length=500), nullable=True))
    op.drop_constraint('fk_shows_root_folder_id', 'shows', type_='foreignkey')
    op.drop_column('shows', 'root_folder_id')

    # Restore root_folder_path and remove root_folder_id from movies
    op.add_column('movies', sa.Column('root_folder_path', sa.String(length=500), nullable=True))
    op.drop_constraint('fk_movies_root_folder_id', 'movies', type_='foreignkey')
    op.drop_column('movies', 'root_folder_id')

    # Drop folder_selection_settings table
    op.drop_table('folder_selection_settings')

    # Drop root_folders table
    op.drop_index('idx_root_folders_media_type', table_name='root_folders')
    op.drop_table('root_folders')
