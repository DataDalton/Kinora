"""add safety templates, the Kinora trusted uploader list, and trust fields on releases and history

media_profiles.safety_template chooses which releases a profile may download (trusted,
balanced or open, see app.services.release_trust). Existing profiles get open, which is
how they behaved before, so none of them change. New profiles default to trusted.

trusted_uploaders is the Kinora trusted list. Each entry stores the name ext.to shows for
a verified account and the name 1337x shows, since the same uploader can go by different
names on each. The seeded entries are marked is_default. Later releases may add default
entries in their own migrations but never remove or edit rows, so entries an administrator
added or changed are kept.

releases (the local release index) and download_history gain the trust fields, so a
cached release keeps its badge and sites, and history records why a release was chosen.

Revision ID: safety_templates
Revises: blocklist_hash
Create Date: 2026-11-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

# Revision identifiers, used by Alembic.
revision: str = "safety_templates"
down_revision: Union[str, None] = "blocklist_hash"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (display name, name on ext.to, name on 1337x). The 1337x names were read from each
# account's 1337x profile page.
DEFAULT_TRUSTED_UPLOADERS = [
    ("QxR", "QxR", "QxR"),
    ("B0NE", "B0NE", "bone111"),
    ("NAHOM1", "NAHOM1", "NAHOM1"),
    ("Vyndros", "Vyndros", "ReVyndros"),
    ("NeoNoir", "NeoNoir", "NeoNoir"),
    ("mazemaze16", "mazemaze16", "mazemaze16"),
    ("TGxGoodies", "TGxGoodies", "TGxGoodies"),
]


def upgrade() -> None:
    op.add_column(
        "media_profiles",
        sa.Column("safety_template", sa.String(length=16), server_default="open", nullable=False),
    )
    op.alter_column("media_profiles", "safety_template", server_default="trusted")

    trusted = op.create_table(
        "trusted_uploaders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("ext_name", sa.String(length=100), nullable=True),
        sa.Column("leetx_name", sa.String(length=100), nullable=True),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("display_name", name="uq_trusted_uploaders_display_name"),
    )
    op.bulk_insert(
        trusted,
        [
            {"display_name": display, "ext_name": ext, "leetx_name": leetx, "is_default": True, "enabled": True}
            for display, ext, leetx in DEFAULT_TRUSTED_UPLOADERS
        ],
    )

    op.add_column("releases", sa.Column("uploader_badge", sa.String(length=20), nullable=True))
    op.add_column("releases", sa.Column("origin_sites", ARRAY(sa.Text()), nullable=True))

    op.add_column("download_history", sa.Column("uploader", sa.String(length=255), nullable=True))
    op.add_column("download_history", sa.Column("trust_category", sa.String(length=20), nullable=True))
    op.add_column("download_history", sa.Column("safety_template", sa.String(length=16), nullable=True))
    op.add_column("download_history", sa.Column("origin_sites", ARRAY(sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("download_history", "origin_sites")
    op.drop_column("download_history", "safety_template")
    op.drop_column("download_history", "trust_category")
    op.drop_column("download_history", "uploader")
    op.drop_column("releases", "origin_sites")
    op.drop_column("releases", "uploader_badge")
    op.drop_table("trusted_uploaders")
    op.drop_column("media_profiles", "safety_template")
