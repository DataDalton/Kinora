"""add info hash and scope to the blocklist

Blocklist rows gain info_hash, identifying one exact torrent, and scope. Scope 'item'
keeps the existing behavior of applying to one media item. Scope 'all' applies to every
item and is used for torrents that failed validation. Existing rows become 'item'.

Revision ID: blocklist_hash
Revises: import_extras_and_cleanup
Create Date: 2026-11-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "blocklist_hash"
down_revision: Union[str, None] = "import_extras_and_cleanup"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("blocklist", sa.Column("info_hash", sa.String(length=64), nullable=True))
    op.add_column("blocklist", sa.Column("scope", sa.String(length=10), server_default="item", nullable=False))
    op.create_index("idx_blocklist_info_hash", "blocklist", ["info_hash"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_blocklist_info_hash", table_name="blocklist")
    op.drop_column("blocklist", "scope")
    op.drop_column("blocklist", "info_hash")
