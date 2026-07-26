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

from app.db import get_db
from app.api.v1.endpoints.auth import get_current_user, require_permission
from app.schemas.user import UserWithPermissions
from app.services.download_clients.qbittorrent import QBittorrentClient
from app.core.config import settings
from app.services.folder_selector import folderSelector

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


async def ensure_bundled_root_folders() -> None:
    """
    Create the library and download root folders on first boot, so the setup wizard needs
    no folder step. Runs only when AUTO_ROOT_FOLDERS is on and no root folders exist yet.
    All four media roots live under MEDIA_ROOT and share the DOWNLOADS_ROOT download
    folder, which is on the same filesystem so completed downloads hardlink in.
    """
    if not settings.AUTO_ROOT_FOLDERS:
        return
    try:
        from app.db import get_pool

        media_root = settings.MEDIA_ROOT
        download_root = settings.DOWNLOADS_ROOT
        folders = [("movies", "Movies"), ("shows", "TV Shows"), ("anime", "Anime"), ("music", "Music")]

        pool = await get_pool()
        async with pool.acquire() as conn:
            # Serialize across worker processes so the check-then-create cannot race.
            async with conn.transaction():
                await conn.execute("SELECT pg_advisory_xact_lock(4915624)")
                existing = await conn.fetchval("SELECT COUNT(*) FROM root_folders")
                if existing:
                    return
                for media_type, name in folders:
                    await folderSelector.createFolder(
                        conn,
                        mediaType=media_type,
                        name=name,
                        rootPath=os.path.join(media_root, media_type),
                        downloadPath=download_root,
                    )
                print(f"[INIT] Auto-created root folders under {media_root}")
    except Exception as e:
        print(f"[INIT] Root folder auto-config skipped: {e}")


async def ensure_bundled_download_client() -> None:
    """
    Register the bundled qBittorrent as the download client on first boot, so the setup
    wizard is not required for the default Docker deployment. Runs only when
    QBITTORRENT_AUTOCONFIG is on and no download client exists yet, so a manually
    configured client is never replaced. qBittorrent bypasses authentication for the
    internal subnet (seeded into its config), so no password is needed here.
    """
    if not settings.QBITTORRENT_AUTOCONFIG:
        return
    try:
        from app.db import get_pool

        pool = await get_pool()
        async with pool.acquire() as conn:
            # Serialize across the worker processes that all run this on startup, so the
            # check-then-insert cannot race into duplicate rows.
            async with conn.transaction():
                await conn.execute("SELECT pg_advisory_xact_lock(4915623)")
                existing = await conn.fetchval("SELECT COUNT(*) FROM download_clients")
                if existing:
                    return
                await conn.execute(
                    """
                    INSERT INTO download_clients (
                        name, client_type, host, port, username, encrypted_password,
                        use_ssl, is_enabled, is_default, test_status
                    )
                    VALUES ($1, 'qbittorrent', $2, $3, $4, $5, FALSE, TRUE, TRUE, 'untested')
                    """,
                    "qBittorrent (bundled)",
                    settings.QBITTORRENT_HOST,
                    settings.QBITTORRENT_PORT,
                    settings.QBITTORRENT_USERNAME,
                    encrypt_value(settings.QBITTORRENT_PASSWORD),
                )
                print(
                    f"[INIT] Registered bundled qBittorrent at "
                    f"{settings.QBITTORRENT_HOST}:{settings.QBITTORRENT_PORT}"
                )
    except Exception as e:
        print(f"[INIT] Bundled qBittorrent auto-config skipped: {e}")


class SetupStatusResponse(BaseModel):
    """Response for setup status check"""

    is_setup_complete: bool
    has_download_client: bool
    has_tmdb_key: bool
    has_root_folders: bool
    is_admin: bool


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


@router.get("/status", response_model=SetupStatusResponse)
async def get_setup_status(
    current_user: UserWithPermissions = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Check if setup is complete and what steps are remaining.
    """
    # Check for download client
    has_download_client = await conn.fetchval("SELECT EXISTS(SELECT 1 FROM download_clients WHERE is_enabled = TRUE)")

    # Check for TMDB key
    tmdb_key_row = await conn.fetchrow("SELECT value FROM app_settings WHERE key = 'tmdb_api_key'")
    has_tmdb_key = bool(tmdb_key_row and tmdb_key_row["value"])

    # Check for root folders - requires at least one active folder per media type
    mediaTypes = ["movies", "shows", "anime", "music"]
    hasAllFolders = True
    for mediaType in mediaTypes:
        folderCount = await conn.fetchval(
            "SELECT COUNT(*) FROM root_folders WHERE media_type = $1 AND is_active = TRUE", mediaType
        )
        if not folderCount or folderCount == 0:
            hasAllFolders = False
            break
    has_root_folders = hasAllFolders

    is_setup_complete = has_download_client and has_tmdb_key and has_root_folders

    # Check if user has system.admin permission
    is_admin = "system.admin" in current_user.permissions

    return SetupStatusResponse(
        is_setup_complete=is_setup_complete,
        has_download_client=has_download_client,
        has_tmdb_key=has_tmdb_key,
        has_root_folders=has_root_folders,
        is_admin=is_admin,
    )


@router.post("/qbittorrent")
async def setup_qbittorrent(
    config: QBittorrentSetupRequest,
    current_user: UserWithPermissions = Depends(require_permission("system.admin")),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Configure qBittorrent download client.
    Only administrators can configure setup.
    """

    # Test connection first
    try:
        client = QBittorrentClient(
            host=config.host,
            port=config.port,
            username=config.username,
            password=config.password,
            use_ssl=config.use_ssl,
        )

        # Test connection
        is_connected = await client.test_connection()

        if not is_connected:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to connect to qBittorrent. Check host, port, and credentials.",
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
        try:
            await client.add_category("music", "/downloads/music")
        except Exception:
            pass

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"qBittorrent connection test failed: {str(e)}"
        )

    # Encrypt password
    encrypted_password = encrypt_value(config.password)

    # Save to database (mark any existing default as non-default)
    await conn.execute("UPDATE download_clients SET is_default = FALSE WHERE is_default = TRUE")

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
        "success",
    )

    return {"status": "success", "message": "qBittorrent configured successfully"}


@router.post("/tmdb")
async def setup_tmdb(
    config: TMDBSetupRequest,
    current_user: UserWithPermissions = Depends(require_permission("system.admin")),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Configure TMDB API key.
    Only administrators can configure setup.
    """

    # Test the API key
    from app.core.http_client import http_get

    try:
        response = await http_get(f"https://api.themoviedb.org/3/configuration?api_key={config.api_key}")
        if response.status_code != 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid TMDB API key")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to validate TMDB API key: {str(e)}"
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
        "TMDB API v3 Key for fetching movie and TV show metadata",
    )

    return {"status": "success", "message": "TMDB API key configured successfully"}


@router.post("/complete")
async def mark_setup_complete(
    current_user: UserWithPermissions = Depends(require_permission("system.admin")),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Mark setup as complete after all steps are done.
    Only administrators can complete setup.
    """

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
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Setup incomplete. Missing: {', '.join(missing)}"
        )

    # Mark setup as complete and initialize system settings
    settings_to_create = [
        (
            "setup_complete",
            "true",
            "boolean",
            False,
            "internal",
            "Indicates if initial setup wizard has been completed",
        ),
        ("allow_user_registration", "true", "boolean", False, "system", "Allow new users to register accounts"),
        ("rss_sync_interval", "15", "integer", False, "system", "RSS feed sync interval in minutes"),
        (
            "auto_search_interval",
            "60",
            "integer",
            False,
            "system",
            "Automatic search interval in minutes for monitored content",
        ),
        (
            "upgrade_search_interval",
            "360",
            "integer",
            False,
            "system",
            "Upgrade search interval in minutes for quality upgrades",
        ),
    ]

    for key, value, value_type, is_encrypted, category, description in settings_to_create:
        await conn.execute(
            """
            INSERT INTO app_settings (key, value, value_type, is_encrypted, category, description)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = NOW()
            """,
            key,
            value,
            value_type,
            is_encrypted,
            category,
            description,
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
    current_user: UserWithPermissions = Depends(require_permission("system.admin")),
):
    """
    Browse filesystem directories for folder selection.
    Only administrators can browse directories.
    """

    try:
        # Handle Windows drive root listing
        import platform

        if platform.system() == "Windows" and (path == "/" or path == ""):
            # List available drives on Windows
            import string
            from pathlib import Path as PathLib

            drives = []
            for letter in string.ascii_uppercase:
                drive_path = f"{letter}:\\"
                if PathLib(drive_path).exists():
                    drives.append(DirectoryItem(name=f"{letter}:", path=drive_path, is_directory=True))
            return BrowseDirectoryResponse(current_path="Computer", parent_path=None, items=drives)

        # Normalize and validate path
        target_path = Path(path).resolve()

        # Check if path exists and is a directory
        if not target_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Path does not exist: {path}")

        if not target_path.is_dir():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Path is not a directory: {path}")

        # Get parent path
        # On Windows, if we're at drive root (e.g., C:\), go back to drive list
        if platform.system() == "Windows" and target_path.parent == target_path:
            parent_path = "/"  # Signal to go back to drive listing
        else:
            parent_path = str(target_path.parent) if target_path.parent != target_path else None

        # List directory contents (directories only)
        items = []
        try:
            for entry in sorted(target_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                # Skip hidden files/folders on Unix
                if entry.name.startswith("."):
                    continue

                try:
                    is_dir = entry.is_dir()
                    items.append(DirectoryItem(name=entry.name, path=str(entry), is_directory=is_dir))
                except PermissionError, OSError:
                    # Skip files/folders we can't access
                    continue

        except PermissionError:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Permission denied accessing: {path}")

        return BrowseDirectoryResponse(current_path=str(target_path), parent_path=parent_path, items=items)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error browsing directory: {str(e)}"
        )
