from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import asyncpg

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user

router = APIRouter()


class SettingUpdate(BaseModel):
    value: str = Field(..., description="The setting value")


class SettingResponse(BaseModel):
    key: str
    value: Optional[str]
    category: str
    description: Optional[str]
    is_sensitive: bool


class SettingsGroupResponse(BaseModel):
    category: str
    settings: List[SettingResponse]


@router.get("/", response_model=List[SettingsGroupResponse])
async def get_all_settings(
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Get all settings grouped by category
    Only superusers can access settings
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can access settings",
        )

    rows = await conn.fetch("""
        SELECT key, value, category, description, is_sensitive
        FROM settings
        ORDER BY category, key
    """)

    settings_by_category: Dict[str, List[SettingResponse]] = {}

    for row in rows:
        category = row["category"] or "general"
        setting = SettingResponse(
            key=row["key"],
            value=row["value"] if not row["is_sensitive"] else "***HIDDEN***",
            category=category,
            description=row["description"],
            is_sensitive=row["is_sensitive"],
        )

        if category not in settings_by_category:
            settings_by_category[category] = []
        settings_by_category[category].append(setting)

    return [
        SettingsGroupResponse(category=cat, settings=settings)
        for cat, settings in settings_by_category.items()
    ]


@router.get("/{key}", response_model=SettingResponse)
async def get_setting(
    key: str,
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Get a specific setting by key
    Only superusers can access settings
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can access settings",
        )

    row = await conn.fetchrow("""
        SELECT key, value, category, description, is_sensitive
        FROM settings
        WHERE key = $1
    """, key)

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Setting '{key}' not found",
        )

    return SettingResponse(
        key=row["key"],
        value=row["value"] if not row["is_sensitive"] else "***HIDDEN***",
        category=row["category"] or "general",
        description=row["description"],
        is_sensitive=row["is_sensitive"],
    )


@router.put("/{key}")
async def update_setting(
    key: str,
    setting_update: SettingUpdate,
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Update a setting value
    Only superusers can update settings
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can update settings",
        )

    result = await conn.execute("""
        INSERT INTO settings (key, value, category, updated_at)
        VALUES ($1, $2, 'api_keys', NOW())
        ON CONFLICT (key)
        DO UPDATE SET value = $2, updated_at = NOW()
    """, key, setting_update.value)

    return {"message": f"Setting '{key}' updated successfully"}


@router.delete("/{key}")
async def delete_setting(
    key: str,
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Delete a setting (resets to default)
    Only superusers can delete settings
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can delete settings",
        )

    result = await conn.execute("""
        DELETE FROM settings WHERE key = $1
    """, key)

    if result == "DELETE 0":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Setting '{key}' not found",
        )

    return {"message": f"Setting '{key}' deleted successfully (reset to default)"}


@router.post("/initialize-defaults")
async def initialize_default_settings(
    conn: asyncpg.Connection = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Initialize default settings if they don't exist
    Only superusers can initialize settings
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can initialize settings",
        )

    default_settings = [
        {
            "key": "tmdb_api_key",
            "value": "",
            "category": "api_keys",
            "description": "TMDB API v3 Key for movie/show metadata. Leave empty to use embedded default.",
            "is_sensitive": True,
        },
    ]

    for setting in default_settings:
        await conn.execute("""
            INSERT INTO settings (key, value, category, description, is_sensitive)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (key) DO NOTHING
        """, setting["key"], setting["value"], setting["category"],
            setting["description"], setting["is_sensitive"])

    return {"message": "Default settings initialized"}
