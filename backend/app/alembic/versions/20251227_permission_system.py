"""add permission system with groups and media requests

Revision ID: permission_system
Revises: multiple_root_folders
Create Date: 2025-12-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'permission_system'
down_revision: Union[str, None] = 'multiple_root_folders'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create permissions table
    op.create_table(
        'permissions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(100), unique=True, nullable=False),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
    )
    op.create_index('idx_permissions_name', 'permissions', ['name'])
    op.create_index('idx_permissions_category', 'permissions', ['category'])

    # Create permission_groups table
    op.create_table(
        'permission_groups',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(100), unique=True, nullable=False),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('color', sa.String(7)),
        sa.Column('is_system', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('priority', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
    )
    op.create_index('idx_permission_groups_name', 'permission_groups', ['name'])
    op.create_index('idx_permission_groups_priority', 'permission_groups', ['priority'])

    # Create permission_group_permissions junction table
    op.create_table(
        'permission_group_permissions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('group_id', sa.Integer(), sa.ForeignKey('permission_groups.id', ondelete='CASCADE'), nullable=False),
        sa.Column('permission_name', sa.String(100), nullable=False),
        sa.UniqueConstraint('group_id', 'permission_name'),
    )
    op.create_index('idx_pgp_group', 'permission_group_permissions', ['group_id'])
    op.create_index('idx_pgp_permission', 'permission_group_permissions', ['permission_name'])

    # Create user_groups junction table
    op.create_table(
        'user_groups',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('group_id', sa.Integer(), sa.ForeignKey('permission_groups.id', ondelete='CASCADE'), nullable=False),
        sa.Column('assigned_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('assigned_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.UniqueConstraint('user_id', 'group_id'),
    )
    op.create_index('idx_user_groups_user', 'user_groups', ['user_id'])
    op.create_index('idx_user_groups_group', 'user_groups', ['group_id'])

    # Create media_requests table
    op.create_table(
        'media_requests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('media_type', sa.String(20), nullable=False),
        sa.Column('external_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('poster_path', sa.String(500)),
        sa.Column('year', sa.Integer()),
        sa.Column('overview', sa.Text()),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text())),
        sa.Column('status', sa.String(20), server_default='pending', nullable=False),
        sa.Column('requested_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('reviewed_at', sa.DateTime()),
        sa.Column('reviewed_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('review_notes', sa.Text()),
        sa.Column('request_notes', sa.Text()),
        sa.Column('media_profile_id', sa.Integer()),
        sa.Column('root_folder_id', sa.Integer(), sa.ForeignKey('root_folders.id', ondelete='SET NULL')),
        sa.Column('auto_search', sa.Boolean(), server_default='true'),
        sa.Column('created_media_id', sa.Integer()),
    )
    op.create_index('idx_media_requests_user', 'media_requests', ['user_id'])
    op.create_index('idx_media_requests_status', 'media_requests', ['status'])
    op.create_index('idx_media_requests_media_type', 'media_requests', ['media_type'])
    op.create_index('idx_media_requests_external', 'media_requests', ['media_type', 'external_id'])

    # Seed default permissions matching core permissions.py definitions
    op.execute("""
        INSERT INTO permissions (name, display_name, description, category) VALUES
        -- System permissions
        ('system.admin', 'System Administrator', 'Full system access with all permissions', 'system'),
        ('system.settings', 'Manage Settings', 'View and modify system settings', 'system'),
        ('system.users', 'Manage Users', 'Create, edit, and delete users', 'system'),
        ('system.groups', 'Manage Groups', 'Create, edit, and delete permission groups', 'system'),
        ('system.logs', 'View Logs', 'View system logs and activity', 'system'),

        -- Movies permissions
        ('movies.view', 'View Movies', 'View movie library and details', 'movies'),
        ('movies.manage', 'Manage Movies', 'Add, edit, and delete movies', 'movies'),
        ('movies.request', 'Request Movies', 'Submit movie requests for approval', 'movies'),
        ('movies.approve', 'Approve Movie Requests', 'Approve or deny movie requests', 'movies'),
        ('movies.download', 'Download Movies', 'Trigger movie downloads and searches', 'movies'),

        -- Shows permissions
        ('shows.view', 'View Shows', 'View TV show library and details', 'shows'),
        ('shows.manage', 'Manage Shows', 'Add, edit, and delete TV shows', 'shows'),
        ('shows.request', 'Request Shows', 'Submit TV show requests for approval', 'shows'),
        ('shows.approve', 'Approve Show Requests', 'Approve or deny TV show requests', 'shows'),
        ('shows.download', 'Download Shows', 'Trigger TV show downloads and searches', 'shows'),

        -- Anime permissions
        ('anime.view', 'View Anime', 'View anime library and details', 'anime'),
        ('anime.manage', 'Manage Anime', 'Add, edit, and delete anime', 'anime'),
        ('anime.request', 'Request Anime', 'Submit anime requests for approval', 'anime'),
        ('anime.approve', 'Approve Anime Requests', 'Approve or deny anime requests', 'anime'),
        ('anime.download', 'Download Anime', 'Trigger anime downloads and searches', 'anime'),

        -- Music permissions
        ('music.view', 'View Music', 'View music library and details', 'music'),
        ('music.manage', 'Manage Music', 'Add, edit, and delete music', 'music'),
        ('music.request', 'Request Music', 'Submit music requests for approval', 'music'),
        ('music.approve', 'Approve Music Requests', 'Approve or deny music requests', 'music'),
        ('music.download', 'Download Music', 'Trigger music downloads and searches', 'music'),

        -- Request management permissions
        ('requests.view', 'View Requests', 'View all pending requests', 'system'),
        ('requests.manage', 'Manage Requests', 'Approve, deny, or modify any request', 'system'),

        -- User password permissions
        ('users.password.self', 'Change Own Password', 'Change your own account password', 'users'),
        ('users.password.reset', 'Reset User Passwords', 'Reset passwords for other users', 'users')
    """)

    # Seed default permission groups
    op.execute("""
        INSERT INTO permission_groups (name, display_name, description, color, is_system, priority) VALUES
        ('administrator', 'Administrator', 'Full system access with all permissions', '#dc2626', true, 100),
        ('media_manager', 'Media Manager', 'Can manage all media and downloads', '#2563eb', true, 80),
        ('request_approver', 'Request Approver', 'Can approve and manage media requests', '#7c3aed', true, 60),
        ('requester', 'Requester', 'Can request new media and view library', '#059669', true, 40),
        ('viewer', 'Viewer', 'Read-only access to media library', '#6b7280', true, 20)
    """)

    # Assign permissions to administrator group (system.admin grants all via hierarchy)
    op.execute("""
        INSERT INTO permission_group_permissions (group_id, permission_name)
        SELECT pg.id, 'system.admin'
        FROM permission_groups pg
        WHERE pg.name = 'administrator'
    """)

    # Assign permissions to media_manager group
    op.execute("""
        INSERT INTO permission_group_permissions (group_id, permission_name)
        SELECT pg.id, p.name
        FROM permission_groups pg
        CROSS JOIN permissions p
        WHERE pg.name = 'media_manager'
        AND p.name IN (
            'movies.manage', 'shows.manage', 'anime.manage', 'music.manage',
            'movies.approve', 'shows.approve', 'anime.approve', 'music.approve',
            'users.password.self'
        )
    """)

    # Assign permissions to request_approver group
    op.execute("""
        INSERT INTO permission_group_permissions (group_id, permission_name)
        SELECT pg.id, p.name
        FROM permission_groups pg
        CROSS JOIN permissions p
        WHERE pg.name = 'request_approver'
        AND p.name IN (
            'movies.view', 'shows.view', 'anime.view', 'music.view',
            'movies.approve', 'shows.approve', 'anime.approve', 'music.approve',
            'requests.view', 'users.password.self'
        )
    """)

    # Assign permissions to requester group
    op.execute("""
        INSERT INTO permission_group_permissions (group_id, permission_name)
        SELECT pg.id, p.name
        FROM permission_groups pg
        CROSS JOIN permissions p
        WHERE pg.name = 'requester'
        AND p.name IN (
            'movies.view', 'shows.view', 'anime.view', 'music.view',
            'movies.request', 'shows.request', 'anime.request', 'music.request',
            'users.password.self'
        )
    """)

    # Assign permissions to viewer group
    op.execute("""
        INSERT INTO permission_group_permissions (group_id, permission_name)
        SELECT pg.id, p.name
        FROM permission_groups pg
        CROSS JOIN permissions p
        WHERE pg.name = 'viewer'
        AND p.name IN ('movies.view', 'shows.view', 'anime.view', 'music.view', 'users.password.self')
    """)

    # Migrate existing users from role column to groups
    # Users with role='administrator' get assigned to 'administrator' group
    op.execute("""
        INSERT INTO user_groups (user_id, group_id)
        SELECT u.id, pg.id
        FROM users u
        CROSS JOIN permission_groups pg
        WHERE u.role = 'administrator' AND pg.name = 'administrator'
    """)

    # Users with role='user' get assigned to 'media_manager' group
    op.execute("""
        INSERT INTO user_groups (user_id, group_id)
        SELECT u.id, pg.id
        FROM users u
        CROSS JOIN permission_groups pg
        WHERE u.role = 'user' AND pg.name = 'media_manager'
    """)

    # Users with any other role or no role get assigned to 'requester' group
    op.execute("""
        INSERT INTO user_groups (user_id, group_id)
        SELECT u.id, pg.id
        FROM users u
        CROSS JOIN permission_groups pg
        WHERE pg.name = 'requester'
        AND u.id NOT IN (SELECT user_id FROM user_groups)
    """)

    # Drop the role column from users table
    op.drop_index('idx_users_role', table_name='users')
    op.drop_column('users', 'role')


def downgrade() -> None:
    # Add back the role column to users table
    op.add_column('users', sa.Column('role', sa.String(50), nullable=True))
    op.create_index('idx_users_role', 'users', ['role'])

    # Migrate users back to role column based on group membership
    # Users in administrator group get role='administrator'
    op.execute("""
        UPDATE users SET role = 'administrator'
        WHERE id IN (
            SELECT ug.user_id FROM user_groups ug
            JOIN permission_groups pg ON pg.id = ug.group_id
            WHERE pg.name = 'administrator'
        )
    """)

    # Users in media_manager group get role='user'
    op.execute("""
        UPDATE users SET role = 'user'
        WHERE role IS NULL AND id IN (
            SELECT ug.user_id FROM user_groups ug
            JOIN permission_groups pg ON pg.id = ug.group_id
            WHERE pg.name = 'media_manager'
        )
    """)

    # All other users get role='user'
    op.execute("""
        UPDATE users SET role = 'user'
        WHERE role IS NULL
    """)

    # Make role column non-nullable
    op.alter_column('users', 'role', nullable=False)

    # Drop media_requests table
    op.drop_index('idx_media_requests_external', table_name='media_requests')
    op.drop_index('idx_media_requests_media_type', table_name='media_requests')
    op.drop_index('idx_media_requests_status', table_name='media_requests')
    op.drop_index('idx_media_requests_user', table_name='media_requests')
    op.drop_table('media_requests')

    # Drop user_groups table
    op.drop_index('idx_user_groups_group', table_name='user_groups')
    op.drop_index('idx_user_groups_user', table_name='user_groups')
    op.drop_table('user_groups')

    # Drop permission_group_permissions table
    op.drop_index('idx_pgp_permission', table_name='permission_group_permissions')
    op.drop_index('idx_pgp_group', table_name='permission_group_permissions')
    op.drop_table('permission_group_permissions')

    # Drop permission_groups table
    op.drop_index('idx_permission_groups_priority', table_name='permission_groups')
    op.drop_index('idx_permission_groups_name', table_name='permission_groups')
    op.drop_table('permission_groups')

    # Drop permissions table
    op.drop_index('idx_permissions_category', table_name='permissions')
    op.drop_index('idx_permissions_name', table_name='permissions')
    op.drop_table('permissions')
