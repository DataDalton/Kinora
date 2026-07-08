"""download gap closers: durable rule timers, transfer history, notifications

Revision ID: download_gap_closers
Revises: download_client_integration
Create Date: 2026-07-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Revision identifiers, used by Alembic.
revision: str = "download_gap_closers"
down_revision: Union[str, None] = "download_client_integration"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Durable per-torrent rule timers (replaces cache-based timers so countdowns
    # survive cache flushes and restarts).
    op.create_table(
        "torrent_rule_state",
        sa.Column("torrent_hash", sa.String(length=100), nullable=False),
        sa.Column("no_peers_since", sa.DateTime(), nullable=True),
        sa.Column("stalled_since", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("torrent_hash", name=op.f("pk_torrent_rule_state")),
    )

    # Time-series transfer stats for the bandwidth/ratio history charts.
    op.create_table(
        "transfer_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("download_speed", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("upload_speed", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("session_download", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("session_upload", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("global_ratio", sa.Float(), server_default="0", nullable=False),
        sa.Column("active_downloads", sa.Integer(), server_default="0", nullable=False),
        sa.Column("active_seeds", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transfer_history")),
    )
    op.create_index("idx_transfer_history_recorded", "transfer_history", ["recorded_at"], unique=False)

    # In-app notifications (VPN alerts, auto-recovery, validation failures, port drift, ...).
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.String(length=20), server_default="info", nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("read", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
    )
    op.create_index("idx_notifications_read", "notifications", ["read"], unique=False)
    op.create_index("idx_notifications_created", "notifications", ["created_at"], unique=False)
    # Dedup key so repeating conditions (e.g. same port drift) don't spam.
    op.create_index("idx_notifications_type", "notifications", ["type"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_notifications_type", table_name="notifications")
    op.drop_index("idx_notifications_created", table_name="notifications")
    op.drop_index("idx_notifications_read", table_name="notifications")
    op.drop_table("notifications")

    op.drop_index("idx_transfer_history_recorded", table_name="transfer_history")
    op.drop_table("transfer_history")

    op.drop_table("torrent_rule_state")
