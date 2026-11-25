"""add extra-file import settings and clear library rows that point into the download folder

Profiles gain import_extra_files and never_import_extensions, which control whether
featurettes, subtitles, images and music companion files come along with the main media.

Imports used to mark an item completed even when no video was found, storing the
torrent's save folder as the item's file. That folder is the download folder shared by
every torrent. Rows whose file_path is a download folder or sits inside one are reset to
wanted with no file, so they are searched again and an upgrade can never treat the
download folder as the item's own file. Nothing on disk is touched.

Revision ID: import_extras_and_cleanup
Revises: fix_quality_and_channel_labels
Create Date: 2026-11-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

# Revision identifiers, used by Alembic.
revision: str = "import_extras_and_cleanup"
down_revision: Union[str, None] = "fix_quality_and_channel_labels"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MEDIA_TABLES = ("movies", "shows", "anime", "albums")


def upgrade() -> None:
    op.add_column(
        "media_profiles",
        sa.Column("import_extra_files", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.add_column("media_profiles", sa.Column("never_import_extensions", ARRAY(sa.Text()), nullable=True))

    inspector = sa.inspect(op.get_bind())
    for table in MEDIA_TABLES:
        columns = {column["name"] for column in inspector.get_columns(table)}
        if not {"file_path", "has_file", "status"} <= columns:
            continue
        clearSize = ", file_size = NULL" if "file_size" in columns else ""
        touch = ", updated_at = NOW()" if "updated_at" in columns else ""
        op.execute(f"""
            UPDATE {table} AS item
            SET status = 'wanted', has_file = FALSE, file_path = NULL{clearSize}{touch}
            WHERE item.file_path IS NOT NULL
              AND EXISTS (
                  SELECT 1 FROM root_folders rf
                  WHERE rtrim(item.file_path, '/') = rtrim(rf.download_path, '/')
                     OR starts_with(item.file_path, rtrim(rf.download_path, '/') || '/')
              )
        """)


def downgrade() -> None:
    op.drop_column("media_profiles", "never_import_extensions")
    op.drop_column("media_profiles", "import_extra_files")
