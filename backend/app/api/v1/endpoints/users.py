from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
import asyncpg

from app.db import get_db
from app.core.security import get_password_hash
from app.api.v1.endpoints.auth import (
    require_permission,
    UserWithPermissions,
)
from app.core.auth_cache import bumpAuthVersion
from app.core.permissions import (
    getUserGroups,
    getUserPermissions,
    setUserGroups,
    validateGroupIds,
    isUserAdmin,
)
from app.schemas.user import (
    UserAdminCreate,
    UserAdminUpdate,
    UserPasswordReset,
    UserGroupsUpdate,
    UserWithPermissions as UserWithPermissionsSchema,
    UserPermissionsResponse,
    PermissionGroup,
)

router = APIRouter()


async def buildUserWithGroups(conn: asyncpg.Connection, userRow: dict) -> dict:
    """Build user dict with groups and permissions"""
    userData = dict(userRow)
    userId = userData["id"]

    # Fetch user's groups
    groups = await getUserGroups(conn, userId)
    userData["groups"] = [PermissionGroup(**g) for g in groups]

    # Fetch user's effective permissions
    permissions = await getUserPermissions(conn, userId)
    userData["permissions"] = list(permissions)

    return userData


@router.get("/", response_model=List[UserWithPermissionsSchema])
async def listUsers(
    conn: asyncpg.Connection = Depends(get_db),
    currentUser: UserWithPermissions = Depends(require_permission("system.users")),
):
    """
    List all users with their groups.
    Requires system.users permission.
    """
    userRows = await conn.fetch("SELECT * FROM users ORDER BY created_at DESC")
    users = []
    for row in userRows:
        userData = await buildUserWithGroups(conn, dict(row))
        users.append(UserWithPermissionsSchema(**userData))
    return users


@router.get("/{userId}", response_model=UserWithPermissionsSchema)
async def getUser(
    userId: int,
    conn: asyncpg.Connection = Depends(get_db),
    currentUser: UserWithPermissions = Depends(require_permission("system.users")),
):
    """
    Get a specific user by ID with their groups and effective permissions.
    Requires system.users permission.
    """
    userRow = await conn.fetchrow("SELECT * FROM users WHERE id = $1", userId)

    if not userRow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    userData = await buildUserWithGroups(conn, dict(userRow))
    return UserWithPermissionsSchema(**userData)


@router.post("/", response_model=UserWithPermissionsSchema, status_code=status.HTTP_201_CREATED)
async def createUser(
    userData: UserAdminCreate,
    conn: asyncpg.Connection = Depends(get_db),
    currentUser: UserWithPermissions = Depends(require_permission("system.users")),
):
    """
    Create a new user with group assignments.
    Requires system.users permission.
    """
    # Check if username exists
    existingUser = await conn.fetchrow(
        "SELECT id FROM users WHERE username = $1",
        userData.username,
    )

    if existingUser:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")

    # Validate group IDs if provided
    if userData.groupIds:
        validGroupIds = await validateGroupIds(conn, userData.groupIds)
        if len(validGroupIds) != len(userData.groupIds):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more group IDs are invalid")

    # Hash password and create user
    hashedPassword = get_password_hash(userData.password)

    userRow = await conn.fetchrow(
        """
        INSERT INTO users (username, hashed_password, is_active)
        VALUES ($1, $2, $3)
        RETURNING *
        """,
        userData.username,
        hashedPassword,
        userData.isActive,
    )

    userId = userRow["id"]

    # Assign user to groups
    if userData.groupIds:
        await setUserGroups(conn, userId, userData.groupIds, currentUser.id)

    await bumpAuthVersion()

    # Build response with groups
    responseData = await buildUserWithGroups(conn, dict(userRow))
    return UserWithPermissionsSchema(**responseData)


@router.put("/{userId}", response_model=UserWithPermissionsSchema)
async def updateUser(
    userId: int,
    userData: UserAdminUpdate,
    conn: asyncpg.Connection = Depends(get_db),
    currentUser: UserWithPermissions = Depends(require_permission("system.users")),
):
    """
    Update a user including group assignments.
    Requires system.users permission.
    """
    # Check if user exists
    existingUser = await conn.fetchrow("SELECT * FROM users WHERE id = $1", userId)

    if not existingUser:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Prevent self-deactivation
    if userId == currentUser.id and userData.isActive is False:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate your own account")

    # Check if new username already exists
    if userData.username and userData.username != existingUser["username"]:
        usernameExists = await conn.fetchrow(
            "SELECT id FROM users WHERE username = $1 AND id != $2",
            userData.username,
            userId,
        )
        if usernameExists:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")

    # Prevent removing admin groups from self if user is admin
    if userId == currentUser.id and userData.groupIds is not None:
        currentIsAdmin = await isUserAdmin(conn, currentUser.id)
        if currentIsAdmin:
            # Validate that admin group is still included
            validGroupIds = await validateGroupIds(conn, userData.groupIds)
            willBeAdmin = False
            for groupId in validGroupIds:
                # Check if any of the new groups has system.admin permission
                hasAdmin = await conn.fetchval(
                    """
                    SELECT EXISTS(
                        SELECT 1 FROM permission_group_permissions
                        WHERE group_id = $1 AND permission_name = 'system.admin'
                    )
                    """,
                    groupId,
                )
                if hasAdmin:
                    willBeAdmin = True
                    break
            if not willBeAdmin:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove your own administrator privileges"
                )

    # Validate group IDs if provided
    if userData.groupIds is not None:
        validGroupIds = await validateGroupIds(conn, userData.groupIds)
        if len(validGroupIds) != len(userData.groupIds):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more group IDs are invalid")

    # Build update query dynamically
    updateFields = []
    updateValues = []
    paramCount = 1

    if userData.username is not None:
        updateFields.append(f"username = ${paramCount}")
        updateValues.append(userData.username)
        paramCount += 1

    if userData.password is not None:
        hashedPassword = get_password_hash(userData.password)
        updateFields.append(f"hashed_password = ${paramCount}")
        updateValues.append(hashedPassword)
        paramCount += 1

    if userData.isActive is not None:
        updateFields.append(f"is_active = ${paramCount}")
        updateValues.append(userData.isActive)
        paramCount += 1

    if updateFields:
        # Add updated_at
        updateFields.append("updated_at = NOW()")

        # Build the final query
        query = f"""
            UPDATE users
            SET {', '.join(updateFields)}
            WHERE id = ${paramCount}
            RETURNING *
        """

        updateValues.append(userId)
        userRow = await conn.fetchrow(query, *updateValues)
    else:
        userRow = existingUser

    # Update group assignments if provided
    if userData.groupIds is not None:
        await setUserGroups(conn, userId, userData.groupIds, currentUser.id)

    await bumpAuthVersion()

    # Build response with groups
    responseData = await buildUserWithGroups(conn, dict(userRow))
    return UserWithPermissionsSchema(**responseData)


@router.delete("/{userId}", status_code=status.HTTP_204_NO_CONTENT)
async def deleteUser(
    userId: int,
    conn: asyncpg.Connection = Depends(get_db),
    currentUser: UserWithPermissions = Depends(require_permission("system.users")),
):
    """
    Delete a user.
    Requires system.users permission.
    """
    # Check if user exists
    existingUser = await conn.fetchrow("SELECT * FROM users WHERE id = $1", userId)

    if not existingUser:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Prevent self-deletion
    if userId == currentUser.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete your own account")

    # Check if this is the last admin user
    userIsAdmin = await isUserAdmin(conn, userId)
    if userIsAdmin:
        # Count users with system.admin permission
        adminCount = await conn.fetchval("""
            SELECT COUNT(DISTINCT ug.user_id)
            FROM user_groups ug
            JOIN permission_group_permissions pgp ON ug.group_id = pgp.group_id
            WHERE pgp.permission_name = 'system.admin'
            """)
        if adminCount <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete the last administrator account"
            )

    await conn.execute("DELETE FROM users WHERE id = $1", userId)

    await bumpAuthVersion()

    return None


@router.put("/{userId}/groups", response_model=UserWithPermissionsSchema)
async def setUserGroupsEndpoint(
    userId: int,
    groupData: UserGroupsUpdate,
    conn: asyncpg.Connection = Depends(get_db),
    currentUser: UserWithPermissions = Depends(require_permission("system.users")),
):
    """
    Set a user's group assignments.
    Requires system.users permission.
    """
    # Check if user exists
    userRow = await conn.fetchrow("SELECT * FROM users WHERE id = $1", userId)

    if not userRow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Validate group IDs
    validGroupIds = await validateGroupIds(conn, groupData.groupIds)
    if len(validGroupIds) != len(groupData.groupIds):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more group IDs are invalid")

    # Prevent removing admin groups from self if user is admin
    if userId == currentUser.id:
        currentIsAdmin = await isUserAdmin(conn, currentUser.id)
        if currentIsAdmin:
            willBeAdmin = False
            for groupId in validGroupIds:
                hasAdmin = await conn.fetchval(
                    """
                    SELECT EXISTS(
                        SELECT 1 FROM permission_group_permissions
                        WHERE group_id = $1 AND permission_name = 'system.admin'
                    )
                    """,
                    groupId,
                )
                if hasAdmin:
                    willBeAdmin = True
                    break
            if not willBeAdmin:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove your own administrator privileges"
                )

    # Set user groups
    await setUserGroups(conn, userId, validGroupIds, currentUser.id)

    await bumpAuthVersion()

    # Build response with groups
    responseData = await buildUserWithGroups(conn, dict(userRow))
    return UserWithPermissionsSchema(**responseData)


@router.get("/{userId}/permissions", response_model=UserPermissionsResponse)
async def getUserPermissionsEndpoint(
    userId: int,
    conn: asyncpg.Connection = Depends(get_db),
    currentUser: UserWithPermissions = Depends(require_permission("system.users")),
):
    """
    Get effective permissions for a user.
    Requires system.users permission.
    """
    # Check if user exists
    userRow = await conn.fetchrow("SELECT * FROM users WHERE id = $1", userId)

    if not userRow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    permissions = await getUserPermissions(conn, userId)

    return UserPermissionsResponse(userId=userId, permissions=list(permissions))


@router.put("/{userId}/password", response_model=UserWithPermissionsSchema)
async def resetUserPassword(
    userId: int,
    passwordData: UserPasswordReset,
    conn: asyncpg.Connection = Depends(get_db),
    currentUser: UserWithPermissions = Depends(require_permission("users.password.reset")),
):
    """
    Reset a user's password.
    Requires users.password.reset permission.
    """
    # Check if user exists
    existingUser = await conn.fetchrow("SELECT * FROM users WHERE id = $1", userId)

    if not existingUser:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Hash new password
    hashedPassword = get_password_hash(passwordData.password)

    userRow = await conn.fetchrow(
        """
        UPDATE users
        SET hashed_password = $1, updated_at = NOW()
        WHERE id = $2
        RETURNING *
        """,
        hashedPassword,
        userId,
    )

    await bumpAuthVersion()

    # Build response with groups
    responseData = await buildUserWithGroups(conn, dict(userRow))
    return UserWithPermissionsSchema(**responseData)


@router.put("/{userId}/toggle-active", response_model=UserWithPermissionsSchema)
async def toggleUserActive(
    userId: int,
    conn: asyncpg.Connection = Depends(get_db),
    currentUser: UserWithPermissions = Depends(require_permission("system.users")),
):
    """
    Toggle user active status.
    Requires system.users permission.
    """
    # Check if user exists
    existingUser = await conn.fetchrow("SELECT * FROM users WHERE id = $1", userId)

    if not existingUser:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Prevent self-deactivation
    if userId == currentUser.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot toggle your own account status")

    newStatus = not existingUser["is_active"]

    userRow = await conn.fetchrow(
        """
        UPDATE users
        SET is_active = $1, updated_at = NOW()
        WHERE id = $2
        RETURNING *
        """,
        newStatus,
        userId,
    )

    await bumpAuthVersion()

    # Build response with groups
    responseData = await buildUserWithGroups(conn, dict(userRow))
    return UserWithPermissionsSchema(**responseData)
