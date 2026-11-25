"""
Kinora trusted uploader list and the safety template descriptions.

Anyone signed in can read the list and the template tables, since the profile editor
shows them. Changing the list needs the system settings permission. Restoring defaults
re-adds and re-enables the seeded entries and leaves entries an administrator added.
"""

from typing import List, Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.v1.endpoints.auth import get_current_user, require_permission
from app.db import get_db
from app.services import release_trust

router = APIRouter()

# The seeded entries, matching the safety_templates migration.
DEFAULT_TRUSTED_UPLOADERS = [
    ("QxR", "QxR", "QxR"),
    ("B0NE", "B0NE", "bone111"),
    ("NAHOM1", "NAHOM1", "NAHOM1"),
    ("Vyndros", "Vyndros", "ReVyndros"),
    ("NeoNoir", "NeoNoir", "NeoNoir"),
    ("mazemaze16", "mazemaze16", "mazemaze16"),
    ("TGxGoodies", "TGxGoodies", "TGxGoodies"),
]


class TrustedUploader(BaseModel):
    id: int
    display_name: str
    ext_name: Optional[str] = None
    leetx_name: Optional[str] = None
    is_default: bool
    enabled: bool


class TrustedUploaderWrite(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=100)
    ext_name: Optional[str] = Field(None, max_length=100)
    leetx_name: Optional[str] = Field(None, max_length=100)
    enabled: bool = True


def _clean(value: Optional[str]) -> Optional[str]:
    value = (value or "").strip()
    return value or None


@router.get("/", response_model=List[TrustedUploader])
async def list_trusted_uploaders(current_user=Depends(get_current_user), conn: asyncpg.Connection = Depends(get_db)):
    rows = await conn.fetch("SELECT * FROM trusted_uploaders ORDER BY is_default DESC, lower(display_name)")
    return [TrustedUploader(**dict(r)) for r in rows]


@router.get("/templates")
async def describe_templates(current_user=Depends(get_current_user)):
    """Every site with its tier, and the uploader categories, for the profile editor's Trust tab."""
    from app.services.indexers.custom import registry

    await registry.ensureLoaded()
    return {
        "templates": list(release_trust.TEMPLATES),
        "default_for_new_profiles": release_trust.DEFAULT_TEMPLATE_FOR_NEW_PROFILES,
        **release_trust.describeTemplate("trusted"),
    }


@router.post("/", response_model=TrustedUploader, status_code=status.HTTP_201_CREATED)
async def add_trusted_uploader(
    body: TrustedUploaderWrite,
    current_user=Depends(require_permission("system.settings")),
    conn: asyncpg.Connection = Depends(get_db),
):
    if not _clean(body.ext_name) and not _clean(body.leetx_name):
        raise HTTPException(status_code=400, detail="Give the uploader's name on ext.to, on 1337x, or both")
    try:
        row = await conn.fetchrow(
            """
            INSERT INTO trusted_uploaders (display_name, ext_name, leetx_name, is_default, enabled)
            VALUES ($1, $2, $3, FALSE, $4) RETURNING *
            """,
            body.display_name.strip(),
            _clean(body.ext_name),
            _clean(body.leetx_name),
            body.enabled,
        )
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=409, detail=f"{body.display_name} is already on the list")
    release_trust.clearTrustedListCache()
    return TrustedUploader(**dict(row))


@router.put("/{entry_id}", response_model=TrustedUploader)
async def update_trusted_uploader(
    entry_id: int,
    body: TrustedUploaderWrite,
    current_user=Depends(require_permission("system.settings")),
    conn: asyncpg.Connection = Depends(get_db),
):
    if not _clean(body.ext_name) and not _clean(body.leetx_name):
        raise HTTPException(status_code=400, detail="Give the uploader's name on ext.to, on 1337x, or both")
    row = await conn.fetchrow(
        """
        UPDATE trusted_uploaders
        SET display_name = $2, ext_name = $3, leetx_name = $4, enabled = $5, updated_at = NOW()
        WHERE id = $1 RETURNING *
        """,
        entry_id,
        body.display_name.strip(),
        _clean(body.ext_name),
        _clean(body.leetx_name),
        body.enabled,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Trusted uploader not found")
    release_trust.clearTrustedListCache()
    return TrustedUploader(**dict(row))


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trusted_uploader(
    entry_id: int,
    current_user=Depends(require_permission("system.settings")),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Delete an entry an administrator added. Default entries are turned off instead, so they can come back."""
    row = await conn.fetchrow("SELECT is_default FROM trusted_uploaders WHERE id = $1", entry_id)
    if not row:
        raise HTTPException(status_code=404, detail="Trusted uploader not found")
    if row["is_default"]:
        raise HTTPException(status_code=400, detail="Default entries can be turned off but not deleted")
    await conn.execute("DELETE FROM trusted_uploaders WHERE id = $1", entry_id)
    release_trust.clearTrustedListCache()


@router.post("/restore-defaults", response_model=List[TrustedUploader])
async def restore_default_uploaders(
    current_user=Depends(require_permission("system.settings")),
    conn: asyncpg.Connection = Depends(get_db),
):
    async with conn.transaction():
        for display, ext, leetx in DEFAULT_TRUSTED_UPLOADERS:
            await conn.execute(
                """
                INSERT INTO trusted_uploaders (display_name, ext_name, leetx_name, is_default, enabled)
                VALUES ($1, $2, $3, TRUE, TRUE)
                ON CONFLICT (display_name) DO UPDATE
                SET ext_name = EXCLUDED.ext_name, leetx_name = EXCLUDED.leetx_name,
                    is_default = TRUE, enabled = TRUE, updated_at = NOW()
                """,
                display,
                ext,
                leetx,
            )
    release_trust.clearTrustedListCache()
    rows = await conn.fetch("SELECT * FROM trusted_uploaders ORDER BY is_default DESC, lower(display_name)")
    return [TrustedUploader(**dict(r)) for r in rows]
