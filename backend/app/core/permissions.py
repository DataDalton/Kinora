"""
Permission system definitions and core functions.

Provides permission definitions, hierarchy mappings, default groups,
and database query functions for checking user permissions.
"""

from typing import Dict, List, Set, Any
import asyncpg

# Permission definitions with display name and category
# Format: 'permission.name': {'displayName': 'Display Name', 'category': 'category'}
PERMISSIONS: Dict[str, Dict[str, str]] = {
    # System permissions
    "system.admin": {
        "displayName": "System Administrator",
        "description": "Full system access with all permissions",
        "category": "system",
    },
    "system.settings": {
        "displayName": "Manage Settings",
        "description": "View and modify system settings",
        "category": "system",
    },
    "system.users": {
        "displayName": "Manage Users",
        "description": "Create, edit, and delete users",
        "category": "system",
    },
    "system.groups": {
        "displayName": "Manage Groups",
        "description": "Create, edit, and delete permission groups",
        "category": "system",
    },
    "system.logs": {
        "displayName": "View Logs",
        "description": "View system logs and activity",
        "category": "system",
    },
    "system.downloads": {
        "displayName": "Manage Downloads",
        "description": "Monitor and control the download client, seeding, and VPN",
        "category": "system",
    },
    # Movies permissions
    "movies.view": {
        "displayName": "View Movies",
        "description": "View movie library and details",
        "category": "movies",
    },
    "movies.manage": {
        "displayName": "Manage Movies",
        "description": "Add, edit, and delete movies",
        "category": "movies",
    },
    "movies.request": {
        "displayName": "Request Movies",
        "description": "Submit movie requests for approval",
        "category": "movies",
    },
    "movies.approve": {
        "displayName": "Approve Movie Requests",
        "description": "Approve or deny movie requests",
        "category": "movies",
    },
    "movies.download": {
        "displayName": "Download Movies",
        "description": "Trigger movie downloads and searches",
        "category": "movies",
    },
    # Shows permissions
    "shows.view": {
        "displayName": "View Shows",
        "description": "View TV show library and details",
        "category": "shows",
    },
    "shows.manage": {
        "displayName": "Manage Shows",
        "description": "Add, edit, and delete TV shows",
        "category": "shows",
    },
    "shows.request": {
        "displayName": "Request Shows",
        "description": "Submit TV show requests for approval",
        "category": "shows",
    },
    "shows.approve": {
        "displayName": "Approve Show Requests",
        "description": "Approve or deny TV show requests",
        "category": "shows",
    },
    "shows.download": {
        "displayName": "Download Shows",
        "description": "Trigger TV show downloads and searches",
        "category": "shows",
    },
    # Anime permissions
    "anime.view": {
        "displayName": "View Anime",
        "description": "View anime library and details",
        "category": "anime",
    },
    "anime.manage": {
        "displayName": "Manage Anime",
        "description": "Add, edit, and delete anime",
        "category": "anime",
    },
    "anime.request": {
        "displayName": "Request Anime",
        "description": "Submit anime requests for approval",
        "category": "anime",
    },
    "anime.approve": {
        "displayName": "Approve Anime Requests",
        "description": "Approve or deny anime requests",
        "category": "anime",
    },
    "anime.download": {
        "displayName": "Download Anime",
        "description": "Trigger anime downloads and searches",
        "category": "anime",
    },
    # Music permissions
    "music.view": {
        "displayName": "View Music",
        "description": "View music library and details",
        "category": "music",
    },
    "music.manage": {
        "displayName": "Manage Music",
        "description": "Add, edit, and delete music",
        "category": "music",
    },
    "music.request": {
        "displayName": "Request Music",
        "description": "Submit music requests for approval",
        "category": "music",
    },
    "music.approve": {
        "displayName": "Approve Music Requests",
        "description": "Approve or deny music requests",
        "category": "music",
    },
    "music.download": {
        "displayName": "Download Music",
        "description": "Trigger music downloads and searches",
        "category": "music",
    },
    # Request management
    "requests.view": {
        "displayName": "View Requests",
        "description": "View all pending requests",
        "category": "system",
    },
    "requests.manage": {
        "displayName": "Manage Requests",
        "description": "Approve, deny, or modify any request",
        "category": "system",
    },
    # User password management
    "users.password.self": {
        "displayName": "Change Own Password",
        "description": "Change your own account password",
        "category": "users",
    },
    "users.password.reset": {
        "displayName": "Reset User Passwords",
        "description": "Reset passwords for other users",
        "category": "users",
    },
}


# Permission hierarchy - parent permissions grant child permissions
# When a user has a parent permission, they implicitly have all child permissions
PERMISSION_HIERARCHY: Dict[str, List[str]] = {
    "system.admin": [
        "system.settings",
        "system.users",
        "system.groups",
        "system.logs",
        "system.downloads",
        "movies.view",
        "movies.manage",
        "movies.request",
        "movies.approve",
        "movies.download",
        "shows.view",
        "shows.manage",
        "shows.request",
        "shows.approve",
        "shows.download",
        "anime.view",
        "anime.manage",
        "anime.request",
        "anime.approve",
        "anime.download",
        "music.view",
        "music.manage",
        "music.request",
        "music.approve",
        "music.download",
        "requests.view",
        "requests.manage",
        "users.password.self",
        "users.password.reset",
    ],
    "system.users": ["users.password.reset"],
    "movies.manage": ["movies.view", "movies.download"],
    "movies.approve": ["movies.view", "requests.view"],
    "shows.manage": ["shows.view", "shows.download"],
    "shows.approve": ["shows.view", "requests.view"],
    "anime.manage": ["anime.view", "anime.download"],
    "anime.approve": ["anime.view", "requests.view"],
    "music.manage": ["music.view", "music.download"],
    "music.approve": ["music.view", "requests.view"],
    "requests.manage": ["requests.view"],
}


# Default permission groups with their configurations
# These are created during initial setup and marked as system groups
DEFAULT_GROUPS: List[Dict[str, Any]] = [
    {
        "name": "administrator",
        "displayName": "Administrator",
        "description": "Full system access with all permissions",
        "color": "#dc2626",
        "isSystem": True,
        "priority": 100,
        "permissions": ["system.admin"],
    },
    {
        "name": "media_manager",
        "displayName": "Media Manager",
        "description": "Can add, edit, and manage all media libraries",
        "color": "#7c3aed",
        "isSystem": True,
        "priority": 80,
        "permissions": [
            "movies.manage",
            "shows.manage",
            "anime.manage",
            "music.manage",
            "movies.approve",
            "shows.approve",
            "anime.approve",
            "music.approve",
            "system.downloads",
            "users.password.self",
        ],
    },
    {
        "name": "request_approver",
        "displayName": "Request Approver",
        "description": "Can approve or deny user requests for media",
        "color": "#2563eb",
        "isSystem": True,
        "priority": 60,
        "permissions": [
            "movies.view",
            "shows.view",
            "anime.view",
            "music.view",
            "movies.approve",
            "shows.approve",
            "anime.approve",
            "music.approve",
            "requests.view",
            "users.password.self",
        ],
    },
    {
        "name": "requester",
        "displayName": "Requester",
        "description": "Can view media and submit requests for new content",
        "color": "#16a34a",
        "isSystem": True,
        "priority": 40,
        "permissions": [
            "movies.view",
            "shows.view",
            "anime.view",
            "music.view",
            "movies.request",
            "shows.request",
            "anime.request",
            "music.request",
            "users.password.self",
        ],
    },
    {
        "name": "viewer",
        "displayName": "Viewer",
        "description": "Can only view media libraries without making changes",
        "color": "#6b7280",
        "isSystem": True,
        "priority": 20,
        "permissions": [
            "movies.view",
            "shows.view",
            "anime.view",
            "music.view",
            "users.password.self",
        ],
    },
]


def expandPermissions(permissions: Set[str]) -> Set[str]:
    """
    Expand permissions based on hierarchy using depth-first search.

    If a user has a parent permission, they implicitly have all child permissions.
    Uses DFS traversal for efficient single-pass expansion.

    Args:
        permissions: Set of permission names to expand

    Returns:
        Expanded set containing original permissions plus all implied child permissions
    """
    expanded = set()
    stack = list(permissions)

    while stack:
        perm = stack.pop()
        if perm in expanded:
            continue
        expanded.add(perm)
        if perm in PERMISSION_HIERARCHY:
            stack.extend(child for child in PERMISSION_HIERARCHY[perm] if child not in expanded)

    return expanded


async def getUserPermissions(conn: asyncpg.Connection, userId: int) -> Set[str]:
    """
    Get all effective permissions for a user.

    Fetches all permission names from groups the user belongs to,
    then expands them based on the permission hierarchy.

    Args:
        conn: Database connection
        userId: User ID to get permissions for

    Returns:
        Set of all permission names the user has (including implied permissions)
    """
    query = """
        SELECT DISTINCT pgp.permission_name
        FROM user_groups ug
        JOIN permission_group_permissions pgp ON ug.group_id = pgp.group_id
        WHERE ug.user_id = $1
    """

    rows = await conn.fetch(query, userId)
    basePermissions = {row["permission_name"] for row in rows}

    return expandPermissions(basePermissions)


async def userHasPermission(conn: asyncpg.Connection, userId: int, permission: str) -> bool:
    """
    Check if a user has a specific permission.

    Args:
        conn: Database connection
        userId: User ID to check
        permission: Permission name to check for

    Returns:
        True if user has the permission (directly or via hierarchy)
    """
    userPermissions = await getUserPermissions(conn, userId)
    return permission in userPermissions


async def userHasAnyPermission(conn: asyncpg.Connection, userId: int, permissions: List[str]) -> bool:
    """
    Check if a user has any of the specified permissions.

    Args:
        conn: Database connection
        userId: User ID to check
        permissions: List of permission names to check for

    Returns:
        True if user has at least one of the permissions
    """
    if not permissions:
        return False

    userPermissions = await getUserPermissions(conn, userId)
    return bool(userPermissions.intersection(permissions))


async def userHasAllPermissions(conn: asyncpg.Connection, userId: int, permissions: List[str]) -> bool:
    """
    Check if a user has all of the specified permissions.

    Args:
        conn: Database connection
        userId: User ID to check
        permissions: List of permission names that are all required

    Returns:
        True if user has all of the permissions
    """
    if not permissions:
        return True

    userPermissions = await getUserPermissions(conn, userId)
    return all(perm in userPermissions for perm in permissions)


async def getUserGroups(conn: asyncpg.Connection, userId: int) -> List[Dict[str, Any]]:
    """
    Get all permission groups a user belongs to.

    Args:
        conn: Database connection
        userId: User ID to get groups for

    Returns:
        List of group records with id, name, displayName, color, and priority
    """
    query = """
        SELECT pg.id, pg.name, pg.display_name, pg.description, pg.color, pg.priority
        FROM user_groups ug
        JOIN permission_groups pg ON ug.group_id = pg.id
        WHERE ug.user_id = $1
        ORDER BY pg.priority DESC
    """

    rows = await conn.fetch(query, userId)
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "displayName": row["display_name"],
            "description": row["description"],
            "color": row["color"],
            "priority": row["priority"],
        }
        for row in rows
    ]


async def getGroupPermissions(conn: asyncpg.Connection, groupId: int) -> List[str]:
    """
    Get all permission names assigned to a group.

    Args:
        conn: Database connection
        groupId: Group ID to get permissions for

    Returns:
        List of permission names assigned to the group
    """
    query = """
        SELECT permission_name
        FROM permission_group_permissions
        WHERE group_id = $1
    """

    rows = await conn.fetch(query, groupId)
    return [row["permission_name"] for row in rows]


async def isUserAdmin(conn: asyncpg.Connection, userId: int) -> bool:
    """
    Check if a user has administrator privileges.

    Args:
        conn: Database connection
        userId: User ID to check

    Returns:
        True if user has system.admin permission
    """
    return await userHasPermission(conn, userId, "system.admin")


async def getGroupByName(conn: asyncpg.Connection, name: str) -> Dict[str, Any] | None:
    """
    Get a permission group by its name.

    Args:
        conn: Database connection
        name: Group name to look up

    Returns:
        Group dictionary or None if not found
    """
    row = await conn.fetchrow(
        """
        SELECT id, name, display_name, description, color, is_system, priority,
               created_at, updated_at
        FROM permission_groups
        WHERE name = $1
        """,
        name,
    )
    if not row:
        return None

    return {
        "id": row["id"],
        "name": row["name"],
        "displayName": row["display_name"],
        "description": row["description"],
        "color": row["color"],
        "isSystem": row["is_system"],
        "priority": row["priority"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


async def assignUserToGroup(
    conn: asyncpg.Connection, userId: int, groupId: int, assignedBy: int | None = None
) -> None:
    """
    Assign a user to a permission group.

    Args:
        conn: Database connection
        userId: User ID to assign
        groupId: Group ID to assign the user to
        assignedBy: ID of user making the assignment (optional)
    """
    await conn.execute(
        """
        INSERT INTO user_groups (user_id, group_id, assigned_by)
        VALUES ($1, $2, $3)
        ON CONFLICT (user_id, group_id) DO NOTHING
        """,
        userId,
        groupId,
        assignedBy,
    )


async def removeUserFromGroup(conn: asyncpg.Connection, userId: int, groupId: int) -> None:
    """
    Remove a user from a permission group.

    Args:
        conn: Database connection
        userId: User ID to remove
        groupId: Group ID to remove the user from
    """
    await conn.execute(
        """
        DELETE FROM user_groups
        WHERE user_id = $1 AND group_id = $2
        """,
        userId,
        groupId,
    )


async def setUserGroups(
    conn: asyncpg.Connection, userId: int, groupIds: List[int], assignedBy: int | None = None
) -> None:
    """
    Set a user's group memberships, replacing any existing memberships.

    Args:
        conn: Database connection
        userId: User ID to update
        groupIds: List of group IDs to assign
        assignedBy: ID of user making the assignment (optional)
    """
    await conn.execute(
        "DELETE FROM user_groups WHERE user_id = $1",
        userId,
    )
    if groupIds:
        await conn.executemany(
            "INSERT INTO user_groups (user_id, group_id, assigned_by) VALUES ($1, $2, $3)",
            [(userId, groupId, assignedBy) for groupId in groupIds],
        )


async def validateGroupIds(conn: asyncpg.Connection, groupIds: List[int]) -> List[int]:
    """
    Validate that all group IDs exist and return the valid ones.

    Args:
        conn: Database connection
        groupIds: List of group IDs to validate

    Returns:
        List of valid group IDs that exist in the database
    """
    if not groupIds:
        return []
    result = await conn.fetch(
        "SELECT id FROM permission_groups WHERE id = ANY($1)",
        groupIds,
    )
    return [r["id"] for r in result]


async def userInGroup(conn: asyncpg.Connection, userId: int, groupName: str) -> bool:
    """
    Check if a user belongs to a specific group by name.

    Args:
        conn: Database connection
        userId: User ID to check
        groupName: Name of the group to check

    Returns:
        True if user is a member of the group
    """
    result = await conn.fetchval(
        """
        SELECT EXISTS(
            SELECT 1
            FROM user_groups ug
            INNER JOIN permission_groups pg ON pg.id = ug.group_id
            WHERE ug.user_id = $1 AND pg.name = $2
        )
        """,
        userId,
        groupName,
    )
    return result
