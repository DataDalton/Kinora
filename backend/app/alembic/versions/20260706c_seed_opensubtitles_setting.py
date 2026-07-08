"""seed the opensubtitles_api_key app setting so it appears in Settings -> API Keys

Revision ID: seed_opensubtitles_setting
Revises: drop_generic_indexers
Create Date: 2026-07-06
"""

from typing import Sequence, Union

from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "seed_opensubtitles_setting"
down_revision: Union[str, None] = "drop_generic_indexers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO app_settings (key, value, value_type, is_encrypted, category, description)
        VALUES ('opensubtitles_api_key', '', 'string', TRUE, 'api_keys',
                'OpenSubtitles API key for subtitle downloads')
        ON CONFLICT (key) DO NOTHING
        """)


def downgrade() -> None:
    op.execute("DELETE FROM app_settings WHERE key = 'opensubtitles_api_key'")
