"""add custom_indexers for user-defined indexers

Each row is one indexer an administrator added: a UNIT3D, Gazelle or Torznab site, a
passkey RSS feed, or a site described by a Kinora definition (kind definition, with the
JSON definition stored in the definition column). credentials holds every secret the
adapter needs (API keys, passkeys, cookies, passwords) as one Fernet-encrypted JSON
object, using the same key as the other secret settings.

trust_tier places the indexer's releases in the safety template system. New indexers
are open, so the Trusted and Balanced templates do not accept them until an
administrator chooses balanced or trusted.

The seeding minimum (min_ratio, min_seed_minutes) is also written to indexer_seed_rules
under the indexer's name by the indexers API, so the existing hit-and-run protection
enforces it.

Revision ID: custom_indexers
Revises: push_subscriptions
Create Date: 2026-11-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

# Revision identifiers, used by Alembic.
revision: str = "custom_indexers"
down_revision: Union[str, None] = "push_subscriptions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "custom_indexers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("base_url", sa.String(length=500), nullable=False),
        sa.Column("settings", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("credentials", sa.Text(), nullable=True),
        sa.Column("definition", JSONB(), nullable=True),
        sa.Column("media_types", ARRAY(sa.Text()), server_default=sa.text("'{}'::text[]"), nullable=False),
        sa.Column("enable_search", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("enable_rss", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("trust_tier", sa.String(length=16), server_default="open", nullable=False),
        sa.Column("is_private", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("min_ratio", sa.Float(), nullable=True),
        sa.Column("min_seed_minutes", sa.Integer(), nullable=True),
        sa.Column("requests_per_minute", sa.Integer(), nullable=True),
        sa.Column("min_interval_seconds", sa.Float(), server_default="2", nullable=False),
        sa.Column("last_test_at", sa.DateTime(), nullable=True),
        sa.Column("last_test_ok", sa.Boolean(), nullable=True),
        sa.Column("last_test_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("name", name="uq_custom_indexers_name"),
        sa.CheckConstraint("trust_tier IN ('open', 'balanced', 'trusted')", name="ck_custom_indexers_trust_tier"),
        sa.CheckConstraint(
            "kind IN ('unit3d', 'gazelle', 'torznab', 'rss', 'definition')", name="ck_custom_indexers_kind"
        ),
    )


def downgrade() -> None:
    op.drop_table("custom_indexers")
