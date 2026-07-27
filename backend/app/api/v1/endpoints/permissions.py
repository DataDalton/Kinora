from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
import asyncpg

from app.db import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.schemas.user import User
from app.schemas.permission import (
    Permission,
    PermissionGroup,
    PermissionGroupCreate,
    PermissionGroupUpdate,
    PermissionGroupSimple,
)
from app.core.permissions import userHasPermission
from app.core.auth_cache import bumpAuthVersion

router = APIRouter()


async def require_user_manage_permission(
    conn: asyncpg.Connection = Depends(get_db), current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency to require system.users or system.groups permission
    """
    hasUsersPermission = await userHasPermission(conn, current_user.id, "system.users")
    hasGroupsPermission = await userHasPermission(conn, current_user.id, "system.groups")
    if not hasUsersPermission and not hasGroupsPermission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to manage users and groups"
        )
    return current_user


@router.get("/", response_model=List[Permission])
async def list_permissions(conn: asyncpg.Connection = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    List all available permissions in the system (authenticated)
    """
    rows = await conn.fetch("""
        SELECT name, display_name, description, category
        FROM permissions
        ORDER BY category, name
        """)

    return [
        Permission(
            name=row["name"],
            display_name=row["display_name"],
            description=row["description"],
            category=row["category"],
        )
        for row in rows
    ]


@router.get("/groups", response_model=List[PermissionGroup])
async def list_permission_groups(
    conn: asyncpg.Connection = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    List all permission groups with their permissions (authenticated)
    """
    # Get all groups
    groupRows = await conn.fetch("""
        SELECT id, name, display_name, description, color, is_system, priority, created_at, updated_at
        FROM permission_groups
        ORDER BY priority DESC, name
        """)

    groups = []
    for row in groupRows:
        # Get permissions for this group
        permRows = await conn.fetch(
            """
            SELECT permission_name
            FROM permission_group_permissions
            WHERE group_id = $1
            ORDER BY permission_name
            """,
            row["id"],
        )

        permissions = [p["permission_name"] for p in permRows]

        groups.append(
            PermissionGroup(
                id=row["id"],
                name=row["name"],
                display_name=row["display_name"],
                description=row["description"],
                color=row["color"],
                is_system=row["is_system"],
                priority=row["priority"],
                permissions=permissions,
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
        )

    return groups


@router.post("/groups", response_model=PermissionGroup, status_code=status.HTTP_201_CREATED)
async def create_permission_group(
    group_data: PermissionGroupCreate,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: User = Depends(require_user_manage_permission),
):
    """
    Create a new custom permission group (requires system.users.manage)
    """
    # Check if group name already exists
    existing = await conn.fetchval("SELECT id FROM permission_groups WHERE name = $1", group_data.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="A permission group with this name already exists"
        )

    # Validate permission names exist
    if group_data.permissionNames:
        validPermissions = await conn.fetch(
            "SELECT name FROM permissions WHERE name = ANY($1)", group_data.permissionNames
        )
        validNames = {p["name"] for p in validPermissions}
        invalidNames = set(group_data.permissionNames) - validNames

        if invalidNames:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid permission names: {', '.join(invalidNames)}"
            )

    # Create the group
    groupRow = await conn.fetchrow(
        """
        INSERT INTO permission_groups (name, display_name, description, color, is_system, priority)
        VALUES ($1, $2, $3, $4, FALSE, 0)
        RETURNING id, name, display_name, description, color, is_system, priority, created_at, updated_at
        """,
        group_data.name,
        group_data.displayName,
        group_data.description,
        group_data.color,
    )

    # Add permissions to the group
    if group_data.permissionNames:
        await conn.executemany(
            "INSERT INTO permission_group_permissions (group_id, permission_name) VALUES ($1, $2)",
            [(groupRow["id"], perm) for perm in group_data.permissionNames],
        )

    await bumpAuthVersion()

    return PermissionGroup(
        id=groupRow["id"],
        name=groupRow["name"],
        display_name=groupRow["display_name"],
        description=groupRow["description"],
        color=groupRow["color"],
        is_system=groupRow["is_system"],
        priority=groupRow["priority"],
        permissions=group_data.permissionNames or [],
        created_at=groupRow["created_at"],
        updated_at=groupRow["updated_at"],
    )


@router.get("/groups/{group_id}", response_model=PermissionGroup)
async def get_permission_group(
    group_id: int, conn: asyncpg.Connection = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Get a specific permission group by ID (authenticated)
    """
    groupRow = await conn.fetchrow(
        """
        SELECT id, name, display_name, description, color, is_system, priority, created_at, updated_at
        FROM permission_groups
        WHERE id = $1
        """,
        group_id,
    )

    if not groupRow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission group not found")

    # Get permissions for this group
    permRows = await conn.fetch(
        """
        SELECT permission_name
        FROM permission_group_permissions
        WHERE group_id = $1
        ORDER BY permission_name
        """,
        group_id,
    )

    permissions = [p["permission_name"] for p in permRows]

    return PermissionGroup(
        id=groupRow["id"],
        name=groupRow["name"],
        display_name=groupRow["display_name"],
        description=groupRow["description"],
        color=groupRow["color"],
        is_system=groupRow["is_system"],
        priority=groupRow["priority"],
        permissions=permissions,
        created_at=groupRow["created_at"],
        updated_at=groupRow["updated_at"],
    )


@router.put("/groups/{group_id}", response_model=PermissionGroup)
async def update_permission_group(
    group_id: int,
    group_data: PermissionGroupUpdate,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: User = Depends(require_user_manage_permission),
):
    """
    Update a permission group (requires system.users.manage)
    System groups cannot have core attributes modified, but permissions can be updated
    """
    # Get existing group
    existingGroup = await conn.fetchrow(
        """
        SELECT id, name, display_name, description, color, is_system, priority, created_at, updated_at
        FROM permission_groups
        WHERE id = $1
        """,
        group_id,
    )

    if not existingGroup:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission group not found")

    # System groups cannot have core attributes modified
    if existingGroup["is_system"]:
        if group_data.displayName is not None or group_data.description is not None or group_data.color is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Cannot modify core attributes of system groups"
            )

    # Validate permission names if provided
    if group_data.permissionNames is not None:
        if group_data.permissionNames:
            validPermissions = await conn.fetch(
                "SELECT name FROM permissions WHERE name = ANY($1)", group_data.permissionNames
            )
            validNames = {p["name"] for p in validPermissions}
            invalidNames = set(group_data.permissionNames) - validNames

            if invalidNames:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid permission names: {', '.join(invalidNames)}",
                )

    # Build update query for non-system groups
    updateFields = []
    updateValues = []
    paramCount = 1

    if group_data.displayName is not None and not existingGroup["is_system"]:
        updateFields.append(f"display_name = ${paramCount}")
        updateValues.append(group_data.displayName)
        paramCount += 1

    if group_data.description is not None and not existingGroup["is_system"]:
        updateFields.append(f"description = ${paramCount}")
        updateValues.append(group_data.description)
        paramCount += 1

    if group_data.color is not None and not existingGroup["is_system"]:
        updateFields.append(f"color = ${paramCount}")
        updateValues.append(group_data.color)
        paramCount += 1

    # Update group attributes if any changed
    if updateFields:
        updateFields.append("updated_at = NOW()")
        query = f"""
            UPDATE permission_groups
            SET {', '.join(updateFields)}
            WHERE id = ${paramCount}
            RETURNING id, name, display_name, description, color, is_system, priority, created_at, updated_at
        """
        updateValues.append(group_id)
        groupRow = await conn.fetchrow(query, *updateValues)
    else:
        # Just update timestamp
        groupRow = await conn.fetchrow(
            """
            UPDATE permission_groups
            SET updated_at = NOW()
            WHERE id = $1
            RETURNING id, name, display_name, description, color, is_system, priority, created_at, updated_at
            """,
            group_id,
        )

    # Update permissions if provided
    if group_data.permissionNames is not None:
        # Delete existing permissions
        await conn.execute("DELETE FROM permission_group_permissions WHERE group_id = $1", group_id)

        # Add new permissions
        if group_data.permissionNames:
            await conn.executemany(
                "INSERT INTO permission_group_permissions (group_id, permission_name) VALUES ($1, $2)",
                [(group_id, perm) for perm in group_data.permissionNames],
            )

    await bumpAuthVersion()

    # Get current permissions
    permRows = await conn.fetch(
        """
        SELECT permission_name
        FROM permission_group_permissions
        WHERE group_id = $1
        ORDER BY permission_name
        """,
        group_id,
    )
    permissions = [p["permission_name"] for p in permRows]

    return PermissionGroup(
        id=groupRow["id"],
        name=groupRow["name"],
        display_name=groupRow["display_name"],
        description=groupRow["description"],
        color=groupRow["color"],
        is_system=groupRow["is_system"],
        priority=groupRow["priority"],
        permissions=permissions,
        created_at=groupRow["created_at"],
        updated_at=groupRow["updated_at"],
    )


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_permission_group(
    group_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: User = Depends(require_user_manage_permission),
):
    """
    Delete a permission group (requires system.users.manage)
    System groups cannot be deleted
    """
    # Get existing group
    existingGroup = await conn.fetchrow("SELECT id, is_system FROM permission_groups WHERE id = $1", group_id)

    if not existingGroup:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission group not found")

    if existingGroup["is_system"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delete system groups")

    # Remove all user associations first
    await conn.execute("DELETE FROM user_groups WHERE group_id = $1", group_id)

    # Remove all permission associations
    await conn.execute("DELETE FROM permission_group_permissions WHERE group_id = $1", group_id)

    # Delete the group
    await conn.execute("DELETE FROM permission_groups WHERE id = $1", group_id)

    await bumpAuthVersion()

    return None
