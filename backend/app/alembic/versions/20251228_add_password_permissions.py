"""add password permissions

Revision ID: add_password_permissions
Revises: permission_system
Create Date: 2025-12-28
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'add_password_permissions'
down_revision: Union[str, None] = 'permission_system'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add password permissions
    op.execute("""
        INSERT INTO permissions (name, display_name, description, category) VALUES
        ('users.password.self', 'Change Own Password', 'Change your own account password', 'users'),
        ('users.password.reset', 'Reset User Passwords', 'Reset passwords for other users', 'users')
        ON CONFLICT (name) DO NOTHING
    """)

    # Add users.password.self to media_manager group
    op.execute("""
        INSERT INTO permission_group_permissions (group_id, permission_name)
        SELECT pg.id, 'users.password.self'
        FROM permission_groups pg
        WHERE pg.name = 'media_manager'
        ON CONFLICT DO NOTHING
    """)

    # Add users.password.self to request_approver group
    op.execute("""
        INSERT INTO permission_group_permissions (group_id, permission_name)
        SELECT pg.id, 'users.password.self'
        FROM permission_groups pg
        WHERE pg.name = 'request_approver'
        ON CONFLICT DO NOTHING
    """)

    # Add users.password.self to requester group
    op.execute("""
        INSERT INTO permission_group_permissions (group_id, permission_name)
        SELECT pg.id, 'users.password.self'
        FROM permission_groups pg
        WHERE pg.name = 'requester'
        ON CONFLICT DO NOTHING
    """)

    # Add users.password.self to viewer group
    op.execute("""
        INSERT INTO permission_group_permissions (group_id, permission_name)
        SELECT pg.id, 'users.password.self'
        FROM permission_groups pg
        WHERE pg.name = 'viewer'
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    # Remove password permissions from groups
    op.execute("""
        DELETE FROM permission_group_permissions
        WHERE permission_name IN ('users.password.self', 'users.password.reset')
    """)

    # Remove password permissions
    op.execute("""
        DELETE FROM permissions
        WHERE name IN ('users.password.self', 'users.password.reset')
    """)
