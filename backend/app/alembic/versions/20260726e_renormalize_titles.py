"""Re-normalize stored release titles

normalizeTitle now removes commas between digits ("10,000" and "10000" normalize
to the same form). Recomputes normalized_title for every existing row with the
SQL equivalent of the Python implementation so stored rows and future queries
agree.

Revision ID: renormalize_titles
Revises: metadata_cache
Create Date: 2026-07-26
"""

from typing import Sequence, Union

from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "renormalize_titles"
down_revision: Union[str, None] = "metadata_cache"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Mirrors release_index.normalizeTitle: lowercase, remove commas between digits,
# collapse remaining non-alphanumerics to single spaces, trim.
_RENORMALIZE_SQL = r"""
    UPDATE releases
    SET normalized_title = trim(
        regexp_replace(
            regexp_replace(lower(title), '(\d),(\d)', '\1\2', 'g'),
            '[^a-z0-9]+', ' ', 'g'
        )
    )
"""


def upgrade() -> None:
    op.execute(_RENORMALIZE_SQL)


def downgrade() -> None:
    # The previous form kept digit commas as spaces. Recompute without the
    # comma-collapse step.
    op.execute(r"""
        UPDATE releases
        SET normalized_title = trim(
            regexp_replace(lower(title), '[^a-z0-9]+', ' ', 'g')
        )
    """)
