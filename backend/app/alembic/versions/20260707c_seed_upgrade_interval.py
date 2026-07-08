"""seed upgrade_search_interval system setting

Revision ID: seed_upgrade_interval
Revises: add_upgrade_replace_policy
Create Date: 2026-07-07
"""

from typing import Sequence, Union

from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "seed_upgrade_interval"
down_revision: Union[str, None] = "add_upgrade_replace_policy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO app_settings (key, value, value_type, is_encrypted, category, description)
        VALUES ('upgrade_search_interval', '360', 'integer', FALSE, 'system',
                'Upgrade search interval in minutes for quality upgrades')
        ON CONFLICT (key) DO NOTHING
        """)


def downgrade() -> None:
    op.execute("DELETE FROM app_settings WHERE key = 'upgrade_search_interval'")
