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

    return [SettingsGroupResponse(category=cat, settings=settings) for cat, settings in settings_by_category.items()]


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
    existing = await conn.fetchrow("SELECT * FROM download_clients WHERE id = $1", client_id)

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Download client with id {client_id} not found"
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
                "UPDATE download_clients SET is_default = FALSE WHERE client_type = $1", existing["client_type"]
            )
        update_fields.append(f"is_default = ${param_count}")
        update_values.append(update_data.is_default)
        param_count += 1

    if not update_fields:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

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
    if existing["client_type"] == "qbittorrent":
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

    row = await conn.fetchrow(
        """
        SELECT key, value, category, description, is_encrypted, value_type
        FROM app_settings
        WHERE key = $1
    """,
        key,
    )

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
    existing = await conn.fetchrow(
        """
        SELECT key, is_encrypted, category
        FROM app_settings
        WHERE key = $1
    """,
        key,
    )

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Setting '{key}' not found",
        )

    # Encrypt value if setting requires encryption
    value_to_store = setting_update.value
    if existing["is_encrypted"]:
        value_to_store = encrypt_value(setting_update.value)

    # Update the setting
    await conn.execute(
        """
        UPDATE app_settings
        SET value = $1, updated_at = NOW()
        WHERE key = $2
    """,
        value_to_store,
        key,
    )

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
    result = await conn.execute(
        """
        UPDATE app_settings
        SET value = '', updated_at = NOW()
        WHERE key = $1
    """,
        key,
    )

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
        {
            "key": "opensubtitles_api_key",
            "value": "",
            "value_type": "string",
            "is_encrypted": True,
            "category": "api_keys",
            "description": "OpenSubtitles API key for subtitle downloads",
        },
    ]

    for setting in default_settings:
        await conn.execute(
            """
            INSERT INTO app_settings (key, value, value_type, is_encrypted, category, description)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (key) DO NOTHING
        """,
            setting["key"],
            setting["value"],
            setting["value_type"],
            setting["is_encrypted"],
            setting["category"],
            setting["description"],
        )

    return {"message": "Default settings initialized"}


# ---- Jellyfin library updates ----
# These routes sit under /jellyfin/ with a second path segment, so the single segment
# /{key} routes above never match them.


class JellyfinPathMapping(BaseModel):
    kinora_path: str = Field(..., description="Path prefix as Kinora sees the library")
    jellyfin_path: str = Field(..., description="The same location as Jellyfin sees it")


class JellyfinLastUpdate(BaseModel):
    state: str
    message: Optional[str] = None
    pathCount: Optional[int] = None
    timestamp: Optional[str] = None


class JellyfinSetupStatus(BaseModel):
    state: str
    message: str


class JellyfinConfigResponse(BaseModel):
    enabled: bool
    url: str
    api_key_set: bool
    path_mappings: List[JellyfinPathMapping]
    last_update: Optional[JellyfinLastUpdate] = None
    # True when the install runs docker-compose.jellyfin.yml, which Kinora links itself.
    bundled: bool = False
    # True while Kinora is linked to the bundled Jellyfin, which needs no path mappings.
    linked_to_bundled: bool = False
    setup_status: Optional[JellyfinSetupStatus] = None


class JellyfinLogin(BaseModel):
    username: str
    password: str
    port: int


class JellyfinConfigUpdate(BaseModel):
    enabled: bool
    url: str = ""
    # None keeps the stored key, an empty string clears it.
    api_key: Optional[str] = None
    path_mappings: List[JellyfinPathMapping] = []


class JellyfinTestRequest(BaseModel):
    # Values typed into the form. Missing values fall back to the stored settings.
    url: Optional[str] = None
    api_key: Optional[str] = None


async def _jellyfinConfigResponse(conn: asyncpg.Connection) -> JellyfinConfigResponse:
    from app.services import jellyfin, jellyfin_setup

    config = await jellyfin.loadConfig(conn)
    lastUpdate = await jellyfin.readStatus()
    setupStatus = jellyfin_setup.readStatus() if jellyfin_setup.isBundled() else None
    return JellyfinConfigResponse(
        enabled=config["enabled"],
        url=config["url"],
        api_key_set=bool(config["apiKey"]),
        path_mappings=[JellyfinPathMapping(**mapping) for mapping in config["pathMappings"]],
        last_update=JellyfinLastUpdate(**lastUpdate) if lastUpdate and lastUpdate.get("state") else None,
        bundled=jellyfin_setup.isBundled(),
        linked_to_bundled=jellyfin_setup.isLinkedToBundled(config),
        setup_status=JellyfinSetupStatus(**setupStatus) if setupStatus else None,
    )


@router.get("/jellyfin/config", response_model=JellyfinConfigResponse)
async def get_jellyfin_config(
    conn: asyncpg.Connection = Depends(get_db),
    current_user: UserWithPermissions = Depends(require_permission("system.admin")),
):
    """Jellyfin connection and path mapping settings. The API key is reported only as set or not set."""
    return await _jellyfinConfigResponse(conn)


@router.get("/jellyfin/login", response_model=JellyfinLogin)
async def get_jellyfin_login(
    current_user: UserWithPermissions = Depends(require_permission("system.admin")),
):
    """Login for the bundled Jellyfin, whose admin password the bootstrap generated."""
    from app.services import jellyfin_setup

    password = jellyfin_setup.adminPassword()
    if not password:
        raise HTTPException(status_code=404, detail="This install does not bundle Jellyfin")
    return JellyfinLogin(username=jellyfin_setup.ADMIN_USERNAME, password=password, port=jellyfin_setup.BUNDLED_PORT)


@router.put("/jellyfin/config", response_model=JellyfinConfigResponse)
async def update_jellyfin_config(
    body: JellyfinConfigUpdate,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: UserWithPermissions = Depends(require_permission("system.admin")),
):
    """Save the Jellyfin settings. Rows are upserted so saving works before the seed migration runs."""
    import json
    from app.services import jellyfin

    url = body.url.strip().rstrip("/")
    if url and not url.lower().startswith(("http://", "https://")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Server URL must start with http:// or https://",
        )

    mappings = jellyfin.parsePathMappings([mapping.model_dump() for mapping in body.path_mappings])

    rows = [
        (
            jellyfin.SETTING_ENABLED,
            "true" if body.enabled else "false",
            "boolean",
            False,
            "Send library changes to Jellyfin",
        ),
        (jellyfin.SETTING_URL, url, "string", False, "Jellyfin server URL"),
        (jellyfin.SETTING_PATH_MAPPINGS, json.dumps(mappings), "json", False, "Kinora to Jellyfin path prefixes"),
    ]
    if body.api_key is not None:
        apiKey = body.api_key.strip()
        rows.append(
            (jellyfin.SETTING_API_KEY, encrypt_value(apiKey) if apiKey else "", "string", True, "Jellyfin API key")
        )

    async with conn.transaction():
        for key, value, valueType, isEncrypted, description in rows:
            await conn.execute(
                """
                INSERT INTO app_settings (key, value, value_type, is_encrypted, category, description)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                """,
                key,
                value,
                valueType,
                isEncrypted,
                jellyfin.SETTINGS_CATEGORY,
                description,
            )

    return await _jellyfinConfigResponse(conn)


@router.post("/jellyfin/test")
async def test_jellyfin_connection(
    body: JellyfinTestRequest,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: UserWithPermissions = Depends(require_permission("system.admin")),
):
    """Call Jellyfin's GET /System/Info with the given or stored URL and API key."""
    from app.services import jellyfin

    stored = await jellyfin.loadConfig(conn)
    url = body.url if body.url is not None and body.url.strip() else stored["url"]
    apiKey = body.api_key if body.api_key is not None and body.api_key.strip() else stored["apiKey"]
    return await jellyfin.testConnection(url, apiKey.strip())


class ReleaseRegionUpdate(BaseModel):
    region: str = Field(..., min_length=2, max_length=2, description="ISO 3166-1 country code")


@router.get("/release-region/config")
async def get_release_region(
    current_user: UserWithPermissions = Depends(require_permission("system.settings")),
):
    """The country whose release dates the calendar uses, plus every country TMDB lists."""
    from app.services.metadata.tmdb import tmdb_service

    tmdb_service.invalidateReleaseRegion()
    region = await tmdb_service.getReleaseRegion()
    try:
        countries = await tmdb_service.getCountries()
    except Exception as e:
        print(f"Error loading TMDB country list: {e}")
        countries = []
    return {"region": region, "countries": countries}


@router.put("/release-region/config")
async def update_release_region(
    body: ReleaseRegionUpdate,
    conn: asyncpg.Connection = Depends(get_db),
    current_user: UserWithPermissions = Depends(require_permission("system.settings")),
):
    """Save the release region and recompute the stored release dates of every movie."""
    from app.services.metadata.tmdb import tmdb_service
    from app.tasks.metadata_refresh import recompute_release_dates

    region = body.region.strip().upper()
    countries = await tmdb_service.getCountries()
    if countries and region not in {country["code"] for country in countries}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown country code {region}")

    await conn.execute(
        """
        INSERT INTO app_settings (key, value, value_type, is_encrypted, category, description)
        VALUES ('release_region', $1, 'string', FALSE, 'metadata', 'Country whose movie release dates are used')
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
        """,
        region,
    )
    tmdb_service.invalidateReleaseRegion()
    recompute_release_dates.delay()
    return {"region": region}
