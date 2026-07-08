"""add upgrade_replace_policy to media_profiles

Controls how an existing file is handled when an upgrade is imported:
keep_old (default, respects no-auto-delete), delete_old, or keep_versions.

Revision ID: add_upgrade_replace_policy
Revises: add_grab_mode
Create Date: 2026-07-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# Revision identifiers, used by Alembic.
revision: str = "add_upgrade_replace_policy"
down_revision: Union[str, None] = "add_grab_mode"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "media_profiles",
        sa.Column("upgrade_replace_policy", sa.String(length=20), server_default="keep_old", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("media_profiles", "upgrade_replace_policy")
