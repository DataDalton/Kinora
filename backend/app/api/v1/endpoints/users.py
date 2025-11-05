from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
import asyncpg

from app.core.database import get_db
from app.core.security import get_password_hash
from app.api.v1.endpoints.auth import get_current_user
from app.schemas.user import User, UserAdminCreate, UserAdminUpdate, UserPasswordReset

router = APIRouter()


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency to require administrator role
    """
    if current_user.role != 'administrator':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can perform this action"
        )
    return current_user


@router.get("/", response_model=List[User])
async def list_users(
    conn: asyncpg.Connection = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    List all users (administrator only)
    """
    users = await conn.fetch("SELECT * FROM users ORDER BY created_at DESC")
    return [User(**dict(user)) for user in users]


@router.get("/{user_id}", response_model=User)
async def get_user(
    user_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Get a specific user by ID (administrator only)
    """
    user_row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)

    if not user_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return User(**dict(user_row))


@router.post("/", response_model=User, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserAdminCreate,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Create a new user (administrator only)
    """
    # Check if username exists
    existing_user = await conn.fetchrow(
        "SELECT id FROM users WHERE username = $1",
        user_data.username,
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )

    # Validate role
    if user_data.role not in ['administrator', 'user']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role. Must be 'administrator' or 'user'"
        )

    # Hash password and create user
    hashed_password = get_password_hash(user_data.password)

    user_row = await conn.fetchrow(
        """
        INSERT INTO users (username, hashed_password, role, is_active)
        VALUES ($1, $2, $3, $4)
        RETURNING *
        """,
        user_data.username,
        hashed_password,
        user_data.role,
        user_data.is_active,
    )

    return User(**dict(user_row))


@router.put("/{user_id}", response_model=User)
async def update_user(
    user_id: int,
    user_data: UserAdminUpdate,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Update a user (administrator only)
    """
    # Check if user exists
    existing_user = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)

    if not existing_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Prevent self-demotion from administrator
    if user_id == current_user.id and user_data.role and user_data.role != 'administrator':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own administrator role"
        )

    # Prevent self-deactivation
    if user_id == current_user.id and user_data.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account"
        )

    # Validate role if provided
    if user_data.role and user_data.role not in ['administrator', 'user']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role. Must be 'administrator' or 'user'"
        )

    # Check if new username already exists
    if user_data.username and user_data.username != existing_user['username']:
        username_exists = await conn.fetchrow(
            "SELECT id FROM users WHERE username = $1 AND id != $2",
            user_data.username,
            user_id,
        )
        if username_exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists"
            )

    # Build update query dynamically
    update_fields = []
    update_values = []
    param_count = 1

    if user_data.username is not None:
        update_fields.append(f"username = ${param_count}")
        update_values.append(user_data.username)
        param_count += 1

    if user_data.password is not None:
        hashed_password = get_password_hash(user_data.password)
        update_fields.append(f"hashed_password = ${param_count}")
        update_values.append(hashed_password)
        param_count += 1

    if user_data.is_active is not None:
        update_fields.append(f"is_active = ${param_count}")
        update_values.append(user_data.is_active)
        param_count += 1

    if user_data.role is not None:
        update_fields.append(f"role = ${param_count}")
        update_values.append(user_data.role)
        param_count += 1

    if not update_fields:
        return User(**dict(existing_user))

    # Add updated_at using NOW() function directly
    update_fields.append("updated_at = NOW()")

    # Build the final query with user_id parameter
    query = f"""
        UPDATE users
        SET {', '.join(update_fields)}
        WHERE id = ${param_count}
        RETURNING *
    """

    # Add user_id as the final parameter
    update_values.append(user_id)

    user_row = await conn.fetchrow(query, *update_values)

    return User(**dict(user_row))


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Delete a user (administrator only)
    """
    # Check if user exists
    existing_user = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)

    if not existing_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Prevent self-deletion
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )

    # Check if this is the last administrator
    if existing_user['role'] == 'administrator':
        admin_count = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE role = 'administrator'"
        )
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete the last administrator account"
            )

    await conn.execute("DELETE FROM users WHERE id = $1", user_id)

    return None


@router.put("/{user_id}/password", response_model=User)
async def reset_user_password(
    user_id: int,
    password_data: UserPasswordReset,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Reset a user's password (administrator only)
    """
    # Check if user exists
    existing_user = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)

    if not existing_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Hash new password
    hashed_password = get_password_hash(password_data.password)

    user_row = await conn.fetchrow(
        """
        UPDATE users
        SET hashed_password = $1, updated_at = NOW()
        WHERE id = $2
        RETURNING *
        """,
        hashed_password,
        user_id,
    )

    return User(**dict(user_row))


@router.put("/{user_id}/toggle-active", response_model=User)
async def toggle_user_active(
    user_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Toggle user active status (administrator only)
    """
    # Check if user exists
    existing_user = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)

    if not existing_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Prevent self-deactivation
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot toggle your own account status"
        )

    new_status = not existing_user['is_active']

    user_row = await conn.fetchrow(
        """
        UPDATE users
        SET is_active = $1, updated_at = NOW()
        WHERE id = $2
        RETURNING *
        """,
        new_status,
        user_id,
    )

    return User(**dict(user_row))
