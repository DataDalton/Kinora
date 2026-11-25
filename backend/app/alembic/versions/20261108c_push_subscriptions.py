"""Web Push subscriptions, one row per browser per user

Each row is a push endpoint a browser handed out after the user allowed notifications,
with the two keys needed to encrypt payloads for it. The endpoint is unique because a
browser profile holds one subscription per origin, so subscribing again on a shared
device moves the row to whoever signed in last. The VAPID key pair lives in
app_settings and is generated on first use, so no seed row is needed here.

Revision ID: push_subscriptions
Revises: jellyfin_settings
Create Date: 2026-11-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# Revision identifiers, used by Alembic.
revision: str = "push_subscriptions"
down_revision: Union[str, None] = "jellyfin_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh", sa.String(length=255), nullable=False),
        sa.Column("auth", sa.String(length=255), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_push_subscriptions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_push_subscriptions")),
        sa.UniqueConstraint("endpoint", name=op.f("uq_push_subscriptions_endpoint")),
    )
    op.create_index("idx_push_subscriptions_user", "push_subscriptions", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_push_subscriptions_user", table_name="push_subscriptions")
    op.drop_table("push_subscriptions")
