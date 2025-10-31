from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import asyncpg

from app.core.database import get_db
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    verify_token,
)
from app.core.config import settings
from app.schemas.user import User, UserCreate, UserLogin, Token

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    conn: asyncpg.Connection = Depends(get_db),
) -> User:
    """
    Get current authenticated user from token
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = verify_token(token, "access")
    if payload is None:
        raise credentials_exception

    username = payload.get("sub")
    if username is None:
        raise credentials_exception

    user_row = await conn.fetchrow("SELECT * FROM users WHERE username = $1", username)

    if user_row is None:
        raise credentials_exception

    return User(**dict(user_row))


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, conn: asyncpg.Connection = Depends(get_db)):
    """
    Register a new user
    """
    # Check if username exists
    existing_user = await conn.fetchrow(
        "SELECT id FROM users WHERE username = $1",
        user_data.username,
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    # Check if this is the first user (should be administrator)
    user_count = await conn.fetchval("SELECT COUNT(*) FROM users")
    is_first_user = user_count == 0
    user_role = 'administrator' if is_first_user else 'user'

    # Hash password and create user
    hashed_password = get_password_hash(user_data.password)

    user_row = await conn.fetchrow(
        """
        INSERT INTO users (username, hashed_password, role)
        VALUES ($1, $2, $3)
        RETURNING *
        """,
        user_data.username,
        hashed_password,
        user_role,
    )

    return User(**dict(user_row))


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    conn: asyncpg.Connection = Depends(get_db)
):
    """
    Login with username and password
    """
    user_row = await conn.fetchrow(
        "SELECT * FROM users WHERE username = $1", form_data.username
    )

    if not user_row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = dict(user_row)

    if not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )

    # Create access and refresh tokens
    access_token = create_access_token(
        data={"sub": user["username"], "user_id": user["id"]}
    )
    refresh_token = create_refresh_token(
        data={"sub": user["username"], "user_id": user["id"]}
    )

    return Token(access_token=access_token, refresh_token=refresh_token)


@router.get("/me", response_model=User)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get current user information
    """
    return current_user
