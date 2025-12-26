"""add validation_mode column to media_profiles

Revision ID: add_validation_mode
Revises: add_anime_series_id
Create Date: 2025-12-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# Revision identifiers, used by Alembic.
revision: str = 'add_validation_mode'
down_revision: Union[str, None] = 'add_anime_series_id'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add validation_mode column to select between blocklist and allowlist validation
    op.add_column(
        'media_profiles',
        sa.Column('validation_mode', sa.String(length=20), server_default='allowlist', nullable=True)
    )

    # Drop the legacy allowed_extensions column (replaced by per-media-type extensions)
    op.drop_column('media_profiles', 'allowed_extensions')


def downgrade() -> None:
    # Restore allowed_extensions column
    op.add_column(
        'media_profiles',
        sa.Column('allowed_extensions', sa.ARRAY(sa.Text()), nullable=True)
    )

    # Drop validation_mode column
    op.drop_column('media_profiles', 'validation_mode')
