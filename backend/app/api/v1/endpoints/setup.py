"""
Setup endpoints for initial application configuration.
First-time setup wizard for configuring download clients, API keys, and root folders.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional, List
from pydantic import BaseModel, Field
import asyncpg
from cryptography.fernet import Fernet
import base64
import hashlib
import os
from pathlib import Path

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.schemas.user import User
from app.services.download_clients.qbittorrent import QBittorrentClient
from app.core.config import settings


router = APIRouter()


# Encryption key derived from SECRET_KEY
def get_encryption_key() -> bytes:
    """Generate encryption key from SECRET_KEY"""
    return base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())


def encrypt_value(value: str) -> str:
    """Encrypt sensitive value"""
    f = Fernet(get_encryption_key())
    return f.encrypt(value.encode()).decode()


def decrypt_value(encrypted_value: str) -> str:
    """Decrypt sensitive value"""
    f = Fernet(get_encryption_key())
    return f.decrypt(encrypted_value.encode()).decode()


class SetupStatusResponse(BaseModel):
    """Response for setup status check"""
    is_setup_complete: bool
    has_download_client: bool
    has_tmdb_key: bool
    has_root_folders: bool
    user_role: str


class QBittorrentSetupRequest(BaseModel):
    """Request to configure qBittorrent"""
    name: str = Field(..., description="Display name for this client")
    host: str = Field(..., description="IP or hostname")
    port: int = Field(..., ge=1, le=65535, description="Port number")
    username: str = Field(..., description="qBittorrent username")
    password: str = Field(..., description="qBittorrent password")
    use_ssl: bool = Field(default=False, description="Use HTTPS")


class TMDBSetupRequest(BaseModel):
    """Request to configure TMDB API key"""
    api_key: str = Field(..., min_length=32, description="TMDB API v3 key")


class RootFoldersSetupRequest(BaseModel):
    """Request to configure root folders"""
    movies_root: str = Field(..., description="Root folder for movies")
    shows_root: str = Field(..., description="Root folder for TV shows")
    anime_root: str = Field(..., description="Root folder for anime")


@router.get("/status", response_model=SetupStatusResponse)
async def get_setup_status(
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Check if setup is complete and what steps are remaining.
    """
    # Check for download client
    has_download_client = await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM download_clients WHERE is_enabled = TRUE)"
    )

    # Check for TMDB key
    tmdb_key_row = await conn.fetchrow(
        "SELECT value FROM app_settings WHERE key = 'tmdb_api_key'"
    )
    has_tmdb_key = bool(tmdb_key_row and tmdb_key_row['value'])

    # Check for root folders
    movies_root = await conn.fetchrow(
        "SELECT value FROM app_settings WHERE key = 'root_folder_movies'"
    )
    shows_root = await conn.fetchrow(
        "SELECT value FROM app_settings WHERE key = 'root_folder_shows'"
    )
    anime_root = await conn.fetchrow(
        "SELECT value FROM app_settings WHERE key = 'root_folder_anime'"
    )
    has_root_folders = bool(movies_root and movies_root['value'] and
                            shows_root and shows_root['value'] and
                            anime_root and anime_root['value'])

    is_setup_complete = has_download_client and has_tmdb_key and has_root_folders

    return SetupStatusResponse(
        is_setup_complete=is_setup_complete,
        has_download_client=has_download_client,
        has_tmdb_key=has_tmdb_key,
        has_root_folders=has_root_folders,
        user_role=current_user.role
    )


@router.post("/qbittorrent")
async def setup_qbittorrent(
    config: QBittorrentSetupRequest,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Configure qBittorrent download client.
    Only administrators can configure setup.
    """
    if current_user.role != 'administrator':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can configure setup"
        )

    # Test connection first
    try:
        client = QBittorrentClient(
            host=config.host,
            port=config.port,
            username=config.username,
            password=config.password,
            use_ssl=config.use_ssl
        )

        # Test connection
        is_connected = await client.test_connection()

        if not is_connected:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to connect to qBittorrent. Check host, port, and credentials."
            )

        # Add default categories for media types (ignore if they already exist)
        try:
            await client.add_category("movies", "/downloads/movies")
        except Exception:
            pass
        try:
            await client.add_category("shows", "/downloads/shows")
        except Exception:
            pass
        try:
            await client.add_category("anime", "/downloads/anime")
        except Exception:
            pass

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"qBittorrent connection test failed: {str(e)}"
        )

    # Encrypt password
    encrypted_password = encrypt_value(config.password)

    # Save to database (mark any existing default as non-default)
    await conn.execute(
        "UPDATE download_clients SET is_default = FALSE WHERE is_default = TRUE"
    )

    await conn.execute(
        """
        INSERT INTO download_clients (
            name, client_type, host, port, username, encrypted_password,
            use_ssl, is_enabled, is_default, test_status, last_tested
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW())
        """,
        config.name,
        "qbittorrent",
        config.host,
        config.port,
        config.username,
        encrypted_password,
        config.use_ssl,
        True,
        True,
        "success"
    )

    return {"status": "success", "message": "qBittorrent configured successfully"}


@router.post("/tmdb")
async def setup_tmdb(
    config: TMDBSetupRequest,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Configure TMDB API key.
    Only administrators can configure setup.
    """
    if current_user.role != 'administrator':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can configure setup"
        )

    # Test the API key
    from app.core.http_client import http_get
    try:
        response = await http_get(
            f"https://api.themoviedb.org/3/configuration?api_key={config.api_key}"
        )
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid TMDB API key"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to validate TMDB API key: {str(e)}"
        )

    # Save encrypted API key
    encrypted_key = encrypt_value(config.api_key)

    # Upsert setting
    await conn.execute(
        """
        INSERT INTO app_settings (key, value, value_type, is_encrypted, category, description)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = NOW()
        """,
        "tmdb_api_key",
        encrypted_key,
        "string",
        True,
        "api_keys",
        "TMDB API v3 Key for fetching movie and TV show metadata"
    )

    return {"status": "success", "message": "TMDB API key configured successfully"}


@router.post("/root-folders")
async def setup_root_folders(
    config: RootFoldersSetupRequest,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Configure root folders for media organization.
    Only administrators can configure setup.
    """
    if current_user.role != 'administrator':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can configure setup"
        )

    # Validate paths exist (optional - you might want to create them)
    import os
    for folder_type, path in [
        ("movies", config.movies_root),
        ("shows", config.shows_root),
        ("anime", config.anime_root)
    ]:
        if not os.path.exists(path):
            try:
                os.makedirs(path, exist_ok=True)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to create {folder_type} folder at {path}: {str(e)}"
                )

    # Save root folders
    folders = [
        ("root_folder_movies", config.movies_root, "Root folder for organizing movie files"),
        ("root_folder_shows", config.shows_root, "Root folder for organizing TV show files"),
        ("root_folder_anime", config.anime_root, "Root folder for organizing anime files"),
    ]

    for key, value, description in folders:
        await conn.execute(
            """
            INSERT INTO app_settings (key, value, value_type, is_encrypted, category, description)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = NOW()
            """,
            key,
            value,
            "string",
            False,
            "paths",
            description
        )

    return {"status": "success", "message": "Root folders configured successfully"}


@router.post("/complete")
async def mark_setup_complete(
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Mark setup as complete after all steps are done.
    Only administrators can complete setup.
    """
    if current_user.role != 'administrator':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can complete setup"
        )

    # Verify all required setup is complete
    status_response = await get_setup_status(current_user, conn)

    if not status_response.is_setup_complete:
        missing = []
        if not status_response.has_download_client:
            missing.append("download client")
        if not status_response.has_tmdb_key:
            missing.append("TMDB API key")
        if not status_response.has_root_folders:
            missing.append("root folders")

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Setup incomplete. Missing: {', '.join(missing)}"
        )

    # Mark setup as complete and initialize system settings
    settings_to_create = [
        ("setup_complete", "true", "boolean", False, "internal", "Indicates if initial setup wizard has been completed"),
        ("allow_user_registration", "true", "boolean", False, "system", "Allow new users to register accounts"),
        ("rss_sync_interval", "15", "integer", False, "system", "RSS feed sync interval in minutes"),
        ("auto_search_interval", "60", "integer", False, "system", "Automatic search interval in minutes for monitored content"),
    ]

    for key, value, value_type, is_encrypted, category, description in settings_to_create:
        await conn.execute(
            """
            INSERT INTO app_settings (key, value, value_type, is_encrypted, category, description)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = NOW()
            """,
            key, value, value_type, is_encrypted, category, description
        )

    return {"status": "success", "message": "Setup completed successfully"}


class DirectoryItem(BaseModel):
    """Response for directory browser item"""
    name: str
    path: str
    is_directory: bool


class BrowseDirectoryResponse(BaseModel):
    """Response for directory browsing"""
    current_path: str
    parent_path: Optional[str]
    items: List[DirectoryItem]


@router.get("/browse-directory", response_model=BrowseDirectoryResponse)
async def browse_directory(
    path: str = "/",
    current_user: User = Depends(get_current_user),
):
    """
    Browse filesystem directories for folder selection.
    Only administrators can browse directories.
    """
    if current_user.role != 'administrator':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can browse directories"
        )

    try:
        # Handle Windows drive root listing
        import platform
        if platform.system() == 'Windows' and (path == '/' or path == ''):
            # List available drives on Windows
            import string
            from pathlib import Path as PathLib
            drives = []
            for letter in string.ascii_uppercase:
                drive_path = f"{letter}:\\"
                if PathLib(drive_path).exists():
                    drives.append(DirectoryItem(
                        name=f"{letter}:",
                        path=drive_path,
                        is_directory=True
                    ))
            return BrowseDirectoryResponse(
                current_path="Computer",
                parent_path=None,
                items=drives
            )

        # Normalize and validate path
        target_path = Path(path).resolve()

        # Check if path exists and is a directory
        if not target_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Path does not exist: {path}"
            )

        if not target_path.is_dir():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Path is not a directory: {path}"
            )

        # Get parent path
        # On Windows, if we're at drive root (e.g., C:\), go back to drive list
        if platform.system() == 'Windows' and target_path.parent == target_path:
            parent_path = "/"  # Signal to go back to drive listing
        else:
            parent_path = str(target_path.parent) if target_path.parent != target_path else None

        # List directory contents (directories only)
        items = []
        try:
            for entry in sorted(target_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                # Skip hidden files/folders on Unix
                if entry.name.startswith('.'):
                    continue

                try:
                    is_dir = entry.is_dir()
                    items.append(DirectoryItem(
                        name=entry.name,
                        path=str(entry),
                        is_directory=is_dir
                    ))
                except (PermissionError, OSError):
                    # Skip files/folders we can't access
                    continue

        except PermissionError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied accessing: {path}"
            )

        return BrowseDirectoryResponse(
            current_path=str(target_path),
            parent_path=parent_path,
            items=items
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error browsing directory: {str(e)}"
        )
