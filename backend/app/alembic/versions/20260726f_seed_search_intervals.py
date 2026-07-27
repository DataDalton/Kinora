"""seed rss_sync_interval and auto_search_interval system settings

The interval dispatcher reads these keys every minute and fell back to its
defaults because the rows never existed, which also kept them out of the
settings UI. Seeds them with the same values the dispatcher used as defaults,
so behavior is unchanged but both become visible and editable.

Revision ID: seed_search_intervals
Revises: renormalize_titles
Create Date: 2026-07-26
"""

from typing import Sequence, Union

from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "seed_search_intervals"
down_revision: Union[str, None] = "renormalize_titles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO app_settings (key, value, value_type, is_encrypted, category, description)
        VALUES
            ('rss_sync_interval', '15', 'integer', FALSE, 'system',
             'New-upload feed check interval in minutes across all indexers'),
            ('auto_search_interval', '60', 'integer', FALSE, 'system',
             'Automatic search interval in minutes for wanted movies and music')
        ON CONFLICT (key) DO NOTHING
        """)


def downgrade() -> None:
    op.execute("DELETE FROM app_settings WHERE key IN ('rss_sync_interval', 'auto_search_interval')")
