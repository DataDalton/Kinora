"""seed the Jellyfin library update settings

Adds the app_settings rows for sending library changes to Jellyfin. The integration
starts disabled. The API key row is stored encrypted like the other API keys.

Revision ID: jellyfin_settings
Revises: metadata_status
Create Date: 2026-11-08
"""

from typing import Sequence, Union

from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "jellyfin_settings"
down_revision: Union[str, None] = "metadata_status"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO app_settings (key, value, value_type, is_encrypted, category, description)
        VALUES
            ('jellyfin_enabled', 'false', 'boolean', FALSE, 'jellyfin',
             'Send library changes to Jellyfin'),
            ('jellyfin_url', '', 'string', FALSE, 'jellyfin',
             'Jellyfin server URL'),
            ('jellyfin_api_key', '', 'string', TRUE, 'jellyfin',
             'Jellyfin API key'),
            ('jellyfin_path_mappings', '[]', 'json', FALSE, 'jellyfin',
             'Kinora to Jellyfin path prefixes')
        ON CONFLICT (key) DO NOTHING
        """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM app_settings
        WHERE key IN ('jellyfin_enabled', 'jellyfin_url', 'jellyfin_api_key', 'jellyfin_path_mappings')
        """)
