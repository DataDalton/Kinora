from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import asyncpg
from cryptography.fernet import Fernet
import base64
import hashlib

from app.db import get_db
from app.api.v1.endpoints.auth import get_current_user, require_permission
from app.schemas.user import UserWithPermissions
from app.core.config import settings as app_config

router = APIRouter()


def get_encryption_key() -> bytes:
    """Generate encryption key from SECRET_KEY"""
    return base64.urlsafe_b64encode(hashlib.sha256(app_config.SECRET_KEY.encode()).digest())


def decrypt_value(encrypted_value: str) -> str:
    """Decrypt sensitive value"""
    try:
        f = Fernet(get_encryption_key())
        return f.decrypt(encrypted_value.encode()).decode()
    except Exception:
        return "***DECRYPTION_ERROR***"


def encrypt_value(value: str) -> str:
    """Encrypt sensitive value"""
    f = Fernet(get_encryption_key())
    return f.encrypt(value.encode()).decode()


class SettingUpdate(BaseModel):
    value: str = Field(..., description="The setting value")


class SettingResponse(BaseModel):
    key: str
    value: Optional[str]
    category: str
    description: Optional[str]
    is_sensitive: bool
    value_type: str


class SettingsGroupResponse(BaseModel):
    category: str
    settings: List[SettingResponse]


class DownloadClientResponse(BaseModel):
    id: int
    name: str
    client_type: str
    host: str
    port: int
    username: str
    use_ssl: bool
    is_enabled: bool
    is_default: bool


class DownloadClientUpdate(BaseModel):
    name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    use_ssl: Optional[bool] = None
    is_enabled: Optional[bool] = None
    is_default: Optional[bool] = None


@router.get("/", response_model=List[SettingsGroupResponse])
async def get_all_settings(
    conn: asyncpg.Connection = Depends(get_db),
    current_user: UserWithPermissions = Depends(require_permission("system.admin")),
):
    """
    Get all settings grouped by category from app_settings table
    Only administrators can access settings
    """

    rows = await conn.fetch("""
        SELECT key, value, category, description, is_encrypted, value_type
        FROM app_settings
        ORDER BY category, key
    """)

    settings_by_category: Dict[str, List[SettingResponse]] = {}

    for row in rows:
        category = row["category"] or "general"

        # Decrypt value if encrypted, but show as hidden for display
        is_encrypted = row["is_encrypted"]
        display_value = "***HIDDEN***" if is_encrypted else row["value"]

        setting = SettingResponse(
            key=row["key"],
            value=display_value,
            category=category,
            description=row["description"],
            is_sensitive=is_encrypted,
            value_type=row["value_type"] or "string",
        )

        if category not in settings_by_category:
            settings_by_category[category] = []
        settings_by_category[category].append(setting)

    return [
        SettingsGroupResponse(category=cat, settings=settings)
        for cat, settings in settings_by_category.items()
    ]


@router.get("/download-clients", response_model=List[DownloadClientResponse])
async def get_download_clients(
    conn: asyncpg.Connection = Depends(get_db),
    current_user: UserWithPermissions = Depends(require_permission("system.admin")),
):
    """
    Get all configured download clients
    Only administrators can access download clients
    """

    rows = await conn.fetch("""
        SELECT id, name, client_type, host, port, username, use_ssl, is_enabled, is_default
        FROM download_clients
        ORDER BY is_default DESC, name
    """)

    return [
        DownloadClientResponse(
            id=row["id"],
            name=row["name"],
            client_type=row["client_type"],
            host=row["host"],
            port=row["port"],
            username=row["username"],
            use_ssl=row["use_ssl"],
            is_enabled=row["is_enabled"],
            is_default=row["is_default"],
        )
        for row in rows
    ]


@router.put("/download-clients/{client_id}", response_model=DownloadClientResponse)
async def update_download_client(
    client_id: int,
    update_data: DownloadClientUpdate,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: UserWithPermissions = Depends(require_permission("system.admin")),
):
    """
    Update a download client configuration
    Only administrators can update download clients
    """

    # Check if client exists
    existing = await conn.fetchrow(
        "SELECT * FROM download_clients WHERE id = $1",
        client_id
    )

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Download client with id {client_id} not found"
        )

    # Build update query dynamically based on provided fields
    update_fields = []
    update_values = []
    param_count = 1

    if update_data.name is not None:
        update_fields.append(f"name = ${param_count}")
        update_values.append(update_data.name)
        param_count += 1

    if update_data.host is not None:
        update_fields.append(f"host = ${param_count}")
        update_values.append(update_data.host)
        param_count += 1

    if update_data.port is not None:
        update_fields.append(f"port = ${param_count}")
        update_values.append(update_data.port)
        param_count += 1

    if update_data.username is not None:
        update_fields.append(f"username = ${param_count}")
        update_values.append(update_data.username)
        param_count += 1

    if update_data.password is not None:
        encrypted_password = encrypt_value(update_data.password)
        update_fields.append(f"encrypted_password = ${param_count}")
        update_values.append(encrypted_password)
        param_count += 1

    if update_data.use_ssl is not None:
        update_fields.append(f"use_ssl = ${param_count}")
        update_values.append(update_data.use_ssl)
        param_count += 1

    if update_data.is_enabled is not None:
        update_fields.append(f"is_enabled = ${param_count}")
        update_values.append(update_data.is_enabled)
        param_count += 1

    if update_data.is_default is not None:
        if update_data.is_default:
            # Unset default for all other clients of same type
            await conn.execute(
                "UPDATE download_clients SET is_default = FALSE WHERE client_type = $1",
                existing['client_type']
            )
        update_fields.append(f"is_default = ${param_count}")
        update_values.append(update_data.is_default)
        param_count += 1

    if not update_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )

    # Add updated_at
    update_fields.append(f"updated_at = NOW()")

    # Build and execute query
    update_query = f"""
        UPDATE download_clients
        SET {', '.join(update_fields)}
        WHERE id = ${param_count}
        RETURNING id, name, client_type, host, port, username, use_ssl, is_enabled, is_default
    """
    update_values.append(client_id)

    updated = await conn.fetchrow(update_query, *update_values)

    # Clear cached qBittorrent client instance so it reloads with new config
    if existing['client_type'] == 'qbittorrent':
        from app.services.download_clients.qbittorrent import qbittorrent_client
        import app.services.download_clients.qbittorrent as qb_module
        qb_module.qbittorrent_client = None

    return DownloadClientResponse(
        id=updated["id"],
        name=updated["name"],
        client_type=updated["client_type"],
        host=updated["host"],
        port=updated["port"],
        username=updated["username"],
        use_ssl=updated["use_ssl"],
        is_enabled=updated["is_enabled"],
        is_default=updated["is_default"],
    )


@router.get("/{key}", response_model=SettingResponse)
async def get_setting(
    key: str,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: UserWithPermissions = Depends(require_permission("system.admin")),
):
    """
    Get a specific setting by key from app_settings table
    Only administrators can access settings
    """

    row = await conn.fetchrow("""
        SELECT key, value, category, description, is_encrypted, value_type
        FROM app_settings
        WHERE key = $1
    """, key)

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Setting '{key}' not found",
        )

    is_encrypted = row["is_encrypted"]
    display_value = "***HIDDEN***" if is_encrypted else row["value"]

    return SettingResponse(
        key=row["key"],
        value=display_value,
        category=row["category"] or "general",
        description=row["description"],
        is_sensitive=is_encrypted,
        value_type=row["value_type"] or "string",
    )


@router.put("/{key}")
async def update_setting(
    key: str,
    setting_update: SettingUpdate,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: UserWithPermissions = Depends(require_permission("system.admin")),
):
    """
    Update a setting value in app_settings table
    Only administrators can update settings
    """

    # Check if setting exists
    existing = await conn.fetchrow("""
        SELECT key, is_encrypted, category
        FROM app_settings
        WHERE key = $1
    """, key)

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Setting '{key}' not found",
        )

    # Encrypt value if setting requires encryption
    value_to_store = setting_update.value
    if existing['is_encrypted']:
        value_to_store = encrypt_value(setting_update.value)

    # Update the setting
    await conn.execute("""
        UPDATE app_settings
        SET value = $1, updated_at = NOW()
        WHERE key = $2
    """, value_to_store, key)

    return {"message": f"Setting '{key}' updated successfully"}


@router.delete("/{key}")
async def delete_setting(
    key: str,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: UserWithPermissions = Depends(require_permission("system.admin")),
):
    """
    Delete a setting (resets to empty/default) from app_settings table
    Only administrators can delete settings
    """

    # Reset value to empty string instead of deleting the row
    result = await conn.execute("""
        UPDATE app_settings
        SET value = '', updated_at = NOW()
        WHERE key = $1
    """, key)

    if result == "UPDATE 0":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Setting '{key}' not found",
        )

    return {"message": f"Setting '{key}' reset to default"}


@router.post("/initialize-defaults")
async def initialize_default_settings(
    conn: asyncpg.Connection = Depends(get_db),
    current_user: UserWithPermissions = Depends(require_permission("system.admin")),
):
    """
    Initialize default settings if they don't exist in app_settings table
    Only administrators can initialize settings
    This is now mostly handled by the setup process, but kept for compatibility
    """

    # Check if settings already exist from setup process
    existing_count = await conn.fetchval("""
        SELECT COUNT(*) FROM app_settings
    """)

    if existing_count > 0:
        return {"message": f"Settings already initialized ({existing_count} settings found)"}

    # Initialize minimal defaults if truly empty
    default_settings = [
        {
            "key": "tmdb_api_key",
            "value": "",
            "value_type": "string",
            "is_encrypted": True,
            "category": "api_keys",
            "description": "TMDB API v3 Key for movie/show metadata",
        },
    ]

    for setting in default_settings:
        await conn.execute("""
            INSERT INTO app_settings (key, value, value_type, is_encrypted, category, description)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (key) DO NOTHING
        """, setting["key"], setting["value"], setting["value_type"],
            setting["is_encrypted"], setting["category"], setting["description"])

    return {"message": "Default settings initialized"}
