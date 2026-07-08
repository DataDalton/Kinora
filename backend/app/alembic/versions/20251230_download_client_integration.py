"""download client integration: validation tracking, seeding cascade, automation, import queue

Revision ID: download_client_integration
Revises: add_password_permissions
Create Date: 2025-12-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Revision identifiers, used by Alembic.
revision: str = "download_client_integration"
down_revision: Union[str, None] = "add_password_permissions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Live validation tracking on download_history ---
    op.add_column(
        "download_history",
        sa.Column("validation_step", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "download_history",
        sa.Column("validation_report", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    # --- Global seeding cascade defaults + automation config on download_clients ---
    op.add_column("download_clients", sa.Column("seed_ratio_limit", sa.Float(), nullable=True))
    op.add_column("download_clients", sa.Column("seed_time_limit", sa.Integer(), nullable=True))
    op.add_column("download_clients", sa.Column("inactive_seed_time_limit", sa.Integer(), nullable=True))
    op.add_column(
        "download_clients", sa.Column("seed_action", sa.String(length=20), server_default="pause", nullable=True)
    )
    op.add_column(
        "download_clients",
        sa.Column("allow_profile_seed_override", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    # Smart-rule, reliability, and gluetun config kept as one JSONB document for flexibility.
    op.add_column(
        "download_clients",
        sa.Column("automation_settings", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
    )

    # --- Per-profile seeding overrides ---
    op.add_column("media_profiles", sa.Column("seed_ratio_limit", sa.Float(), nullable=True))
    op.add_column("media_profiles", sa.Column("seed_time_limit", sa.Integer(), nullable=True))
    op.add_column("media_profiles", sa.Column("inactive_seed_time_limit", sa.Integer(), nullable=True))
    op.add_column(
        "media_profiles", sa.Column("seed_then_cleanup", sa.Boolean(), server_default=sa.text("false"), nullable=False)
    )
    op.add_column("media_profiles", sa.Column("auto_recovery", sa.Boolean(), nullable=True))

    # --- Per-indexer hit-and-run protection rules ---
    op.create_table(
        "indexer_seed_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("indexer", sa.String(length=100), nullable=False),
        sa.Column("min_ratio", sa.Float(), server_default="0", nullable=False),
        sa.Column("min_seed_minutes", sa.Integer(), server_default="0", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_indexer_seed_rules")),
        sa.UniqueConstraint("indexer", name=op.f("uq_indexer_seed_rules_indexer")),
    )

    # --- Manual import queue for files that could not be auto-organized ---
    op.create_table(
        "import_queue",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("torrent_hash", sa.String(length=100), nullable=False),
        sa.Column("torrent_name", sa.Text(), nullable=True),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=True),
        sa.Column("media_type", sa.String(length=20), nullable=True),
        sa.Column("media_id", sa.Integer(), nullable=True),
        sa.Column("suggested_media_id", sa.Integer(), nullable=True),
        sa.Column("suggested_title", sa.Text(), nullable=True),
        sa.Column("season_number", sa.Integer(), nullable=True),
        sa.Column("episode_number", sa.Integer(), nullable=True),
        sa.Column("root_folder_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_queue")),
    )
    op.create_index("idx_import_queue_status", "import_queue", ["status"], unique=False)
    op.create_index("idx_import_queue_hash", "import_queue", ["torrent_hash"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_import_queue_hash", table_name="import_queue")
    op.drop_index("idx_import_queue_status", table_name="import_queue")
    op.drop_table("import_queue")
    op.drop_table("indexer_seed_rules")

    op.drop_column("media_profiles", "auto_recovery")
    op.drop_column("media_profiles", "seed_then_cleanup")
    op.drop_column("media_profiles", "inactive_seed_time_limit")
    op.drop_column("media_profiles", "seed_time_limit")
    op.drop_column("media_profiles", "seed_ratio_limit")

    op.drop_column("download_clients", "automation_settings")
    op.drop_column("download_clients", "allow_profile_seed_override")
    op.drop_column("download_clients", "seed_action")
    op.drop_column("download_clients", "inactive_seed_time_limit")
    op.drop_column("download_clients", "seed_time_limit")
    op.drop_column("download_clients", "seed_ratio_limit")

    op.drop_column("download_history", "validation_report")
    op.drop_column("download_history", "validation_step")
