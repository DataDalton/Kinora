"""Movie release dates

Adds digital_release_date, physical_release_date and theatrical_release_date to movies.
They hold the dates from TMDB's release_dates for the configured region, so the calendar
can place a movie on the day it becomes downloadable rather than its cinema date. The
metadata refresh fills them in.

Revision ID: movie_release_dates
Revises: custom_indexers
Create Date: 2026-11-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# Revision identifiers, used by Alembic.
revision: str = "movie_release_dates"
down_revision: Union[str, None] = "custom_indexers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMNS = ["digital_release_date", "physical_release_date", "theatrical_release_date"]


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = {c["name"] for c in inspector.get_columns("movies")}
    for column in COLUMNS:
        if column not in existing:
            op.add_column("movies", sa.Column(column, sa.Date(), nullable=True))


def downgrade() -> None:
    for column in COLUMNS:
        op.drop_column("movies", column)
