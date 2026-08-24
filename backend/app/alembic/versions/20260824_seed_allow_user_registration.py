"""seed the allow_user_registration system setting

The auth endpoints read this key and treat a missing row as registration being
open, so the row was only ever created by the setup wizard. Instances that
completed setup before the key was added have no row at all, which makes the
generic settings PUT return 404 and leaves the toggle unusable. Seeds it with
the value the auth endpoints already fall back to, so behavior is unchanged but
it becomes visible and editable.

Revision ID: seed_allow_user_registration
Revises: seed_search_intervals
Create Date: 2026-08-24
"""

from typing import Sequence, Union

from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "seed_allow_user_registration"
down_revision: Union[str, None] = "seed_search_intervals"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO app_settings (key, value, value_type, is_encrypted, category, description)
        VALUES ('allow_user_registration', 'true', 'boolean', FALSE, 'system',
                'Allow new users to register accounts')
        ON CONFLICT (key) DO NOTHING
        """)


def downgrade() -> None:
    op.execute("DELETE FROM app_settings WHERE key = 'allow_user_registration'")
