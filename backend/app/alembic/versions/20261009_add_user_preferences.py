"""add a per-user preferences column

Holds settings that belong to one account rather than the whole instance, such as
whether notification sounds play. A JSON object keeps new preferences from needing a
migration each, and the empty default means every existing user starts on the
defaults the application defines.

Revision ID: add_user_preferences
Revises: seed_allow_user_registration
Create Date: 2026-10-09
"""

from typing import Sequence, Union

from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "add_user_preferences"
down_revision: Union[str, None] = "seed_allow_user_registration"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS preferences JSONB NOT NULL DEFAULT '{}'::jsonb")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS preferences")
