"""
User-defined indexers: UNIT3D, Gazelle, Torznab, passkey RSS feeds and Kinora definitions.

Managing indexers needs the system settings permission. Credentials are stored encrypted
and only ever returned masked. On update a credential sent back as the mask keeps the
stored value, an empty one clears it, and anything else replaces it.

Saving an indexer also writes its seeding minimum to indexer_seed_rules under the
indexer's name, where the hit-and-run protection reads it. Renaming or deleting an
indexer leaves the rule of the old name in place, because torrents downloaded under that
name still need it. It can be removed in the download client settings.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.v1.endpoints.auth import get_current_user, require_permission
from app.db import get_db
from app.services import indexer_health
from app.services.indexers.custom import registry
from app.services.indexers.custom.common import TRUST_TIERS, DEFAULT_TRUST_TIER, IndexerConfig
from app.services.indexers.custom.definition import (
    DefinitionError,
    credentialLabels,
    parseDefinitionText,
    validateDefinition,
)
from app.services.indexers.custom.templates import TEMPLATES
from app.services.indexers.search_context import SCOPES, scopeFor

router = APIRouter()

# Sent in place of a stored credential. Sending it back unchanged keeps the stored value.
MASK = "********"


class IndexerWrite(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    kind: str
    base_url: str = ""
    settings: Dict[str, Any] = Field(default_factory=dict)
    credentials: Dict[str, Optional[str]] = Field(default_factory=dict)
    # A JSON object, or its text as typed in the editor.
    definition: Optional[Union[Dict[str, Any], str]] = None
    media_types: List[str] = Field(default_factory=list)
    enable_search: bool = True
    enable_rss: bool = False
    trust_tier: str = DEFAULT_TRUST_TIER
    is_private: bool = True
    min_ratio: Optional[float] = Field(None, ge=0, le=1000)
    min_seed_minutes: Optional[int] = Field(None, ge=0)
    requests_per_minute: Optional[int] = Field(None, ge=1, le=600)
    min_interval_seconds: float = Field(2.0, ge=0, le=3600)


class IndexerToggles(BaseModel):
    enable_search: Optional[bool] = None
    enable_rss: Optional[bool] = None


class TestRequest(BaseModel):
    query: Optional[str] = None
    media_type: Optional[str] = None


class UnsavedTestRequest(IndexerWrite):
    # The saved indexer whose stored credentials fill in masked values, when editing one.
    id: Optional[int] = None
    query: Optional[str] = None
    test_media_type: Optional[str] = None


class DefinitionCheck(BaseModel):
    definition: Union[Dict[str, Any], str]


def _invalid(message: str, errors: Optional[List[str]] = None) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={"message": message, "errors": errors or [message]},
    )


def _adapter(kind: str):
    adapter = registry.ADAPTERS.get(kind)
    if adapter is None:
        raise _invalid(f"Unknown indexer type '{kind}'. Choose one of {', '.join(registry.ADAPTERS)}")
    return adapter


def _credentialKeys(kind: str, definition: Optional[Dict[str, Any]]) -> List[str]:
    if kind == "definition":
        return [key for key, _label in credentialLabels(definition or {})]
    return [spec.key for spec in _adapter(kind).credentialFields()]


def _parseDefinition(value: Union[Dict[str, Any], str, None]) -> Optional[Dict[str, Any]]:
    if value is None or value == "":
        return None
    if isinstance(value, dict):
        return value
    try:
        return parseDefinitionText(value)
    except DefinitionError as e:
        raise _invalid("The definition is not valid JSON", e.errors)


def _normalizeSettings(settings: Dict[str, Any]) -> Dict[str, Any]:
    """Settings with categories as lists of id strings per scope, and empty values dropped."""
    cleaned: Dict[str, Any] = {}
    for key, value in (settings or {}).items():
        if key == "categories":
            if not isinstance(value, dict):
                continue
            categories = {}
            for scope, ids in value.items():
                if scope not in SCOPES:
                    continue
                if isinstance(ids, str):
                    ids = [part.strip() for part in ids.split(",")]
                ids = [str(item).strip() for item in (ids or []) if str(item).strip()]
                if ids:
                    categories[scope] = ids
            if categories:
                cleaned["categories"] = categories
        elif value not in (None, ""):
            cleaned[key] = value.strip() if isinstance(value, str) else value
    return cleaned


async def _prepare(conn, body: IndexerWrite, existing: Optional[asyncpg.Record]) -> Dict[str, Any]:
    """Validate a create or update and return the column values to store. Raises 422 with every problem."""
    errors: List[str] = []
    name = body.name.strip()
    if name.lower() in registry.RESERVED_NAMES:
        errors.append(f"'{name}' is used by a built-in indexer. Choose another name")
    clash = await conn.fetchval(
        "SELECT id FROM custom_indexers WHERE lower(name) = lower($1) AND id <> $2",
        name,
        existing["id"] if existing else 0,
    )
    if clash:
        errors.append(f"Another indexer is already named '{name}'")

    adapter = _adapter(body.kind)
    definition = _parseDefinition(body.definition) if body.kind == "definition" else None
    if body.kind == "definition" and definition is None:
        errors.append("A definition is required for this indexer type")

    mediaTypes = [scope for scope in dict.fromkeys(body.media_types) if scope in SCOPES]
    if body.kind == "gazelle" and not mediaTypes:
        mediaTypes = ["music"]
    if not mediaTypes:
        errors.append("Choose at least one media type")
    if body.trust_tier not in TRUST_TIERS:
        errors.append(f"Trust tier must be one of {', '.join(TRUST_TIERS)}")

    stored = registry.decryptCredentials(existing["credentials"]) if existing else {}
    allowedKeys = _credentialKeys(body.kind, definition)
    credentials: Dict[str, str] = {}
    for key in allowedKeys:
        if key in body.credentials:
            value = body.credentials[key]
            if value == MASK:
                if key in stored:
                    credentials[key] = stored[key]
            elif value not in (None, ""):
                credentials[key] = str(value).strip()
        elif key in stored:
            credentials[key] = stored[key]

    settings = _normalizeSettings(body.settings)
    baseUrl = (body.base_url or "").strip().rstrip("/")
    if not baseUrl and body.kind == "rss" and credentials.get("feedUrl"):
        from urllib.parse import urlsplit

        parts = urlsplit(credentials["feedUrl"])
        baseUrl = f"{parts.scheme}://{parts.netloc}"
    if not baseUrl and definition and isinstance(definition.get("baseUrl"), str):
        baseUrl = definition["baseUrl"].strip().rstrip("/")

    errors.extend(adapter.validateConfig(baseUrl, settings, credentials, definition))
    if body.enable_rss and not adapter.supportsRss:
        errors.append(f"{adapter.label} indexers have no feed for RSS monitoring")
    if errors:
        raise _invalid("The indexer could not be saved", errors)

    return {
        "name": name,
        "kind": body.kind,
        "base_url": baseUrl,
        "settings": settings,
        "credentials": registry.encryptCredentials(credentials),
        "credentialsPlain": credentials,
        "definition": definition,
        "media_types": mediaTypes,
        "enable_search": body.enable_search,
        "enable_rss": body.enable_rss,
        "trust_tier": body.trust_tier,
        "is_private": body.is_private,
        "min_ratio": body.min_ratio if body.min_ratio else None,
        "min_seed_minutes": body.min_seed_minutes if body.min_seed_minutes else None,
        "requests_per_minute": body.requests_per_minute,
        "min_interval_seconds": body.min_interval_seconds,
    }


# Media profile column holding the indexer list for each indexer scope.
PROFILE_INDEXER_COLUMNS = {
    "movies": "movie_indexers",
    "shows": "show_indexers",
    "anime": "anime_indexers",
    "music": "music_indexers",
}


async def _syncProfileIndexers(
    conn, oldName: Optional[str], newName: Optional[str], oldScopes: List[str], newScopes: List[str]
) -> None:
    """
    Keep media profile indexer lists in step with a user-defined indexer.

    A rename replaces the old name in every list. A scope the indexer gains appends it
    to that scope's list in every profile, and a scope it loses removes it. Deleting the
    indexer (newName None) removes it everywhere. Empty lists are left empty, since an
    empty list already means every indexer is searched.
    """
    for scope, column in PROFILE_INDEXER_COLUMNS.items():
        if oldName and newName and oldName != newName:
            await conn.execute(
                f"UPDATE media_profiles SET {column} = array_replace({column}, $1, $2)", oldName, newName
            )
        if oldName and (newName is None or (scope in oldScopes and scope not in newScopes)):
            # After a rename the list already holds the new name, so that is the one removed.
            removeName = newName or oldName
            await conn.execute(f"UPDATE media_profiles SET {column} = array_remove({column}, $1)", removeName)
        if newName and scope in newScopes and scope not in oldScopes:
            await conn.execute(
                f"""
                UPDATE media_profiles SET {column} = array_append({column}, $1)
                WHERE cardinality({column}) > 0 AND NOT ($1 = ANY({column}))
                """,
                newName,
            )


async def _syncSeedRule(conn, name: str, minRatio: Optional[float], minSeedMinutes: Optional[int]) -> None:
    """Write the indexer's seeding minimum to indexer_seed_rules, where hit-and-run protection reads it."""
    if (minRatio or 0) > 0 or (minSeedMinutes or 0) > 0:
        await conn.execute(
            """
            INSERT INTO indexer_seed_rules (indexer, min_ratio, min_seed_minutes, enabled)
            VALUES ($1, $2, $3, TRUE)
            ON CONFLICT (indexer) DO UPDATE SET
                min_ratio = EXCLUDED.min_ratio,
                min_seed_minutes = EXCLUDED.min_seed_minutes,
                enabled = TRUE,
                updated_at = NOW()
            """,
            name,
            float(minRatio or 0),
            int(minSeedMinutes or 0),
        )
    else:
        await conn.execute(
            "UPDATE indexer_seed_rules SET enabled = FALSE, updated_at = NOW() WHERE indexer = $1",
            name,
        )


def _jsonColumn(value, fallback):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return fallback
    return value if value is not None else fallback


def _healthStatus(row, health: Dict[str, Any]) -> str:
    if not row["enable_search"] and not row["enable_rss"]:
        return "disabled"
    if health["failures"] >= indexer_health.FAILURES_BEFORE_ALERT:
        return "failing"
    if health["failures"] > 0 or row["last_test_ok"] is False:
        return "warning"
    if row["last_test_ok"] is None:
        return "untested"
    return "ok"


async def _toOut(row) -> Dict[str, Any]:
    definition = _jsonColumn(row["definition"], None)
    stored = registry.decryptCredentials(row["credentials"])
    try:
        keys = _credentialKeys(row["kind"], definition)
    except HTTPException:
        keys = list(stored)
    health = await indexer_health.get_state(row["name"])
    adapter = registry.ADAPTERS.get(row["kind"])
    return {
        "id": row["id"],
        "name": row["name"],
        "kind": row["kind"],
        "kind_label": adapter.label if adapter else row["kind"],
        "base_url": row["base_url"],
        "settings": _jsonColumn(row["settings"], {}),
        "credentials": {key: (MASK if stored.get(key) else "") for key in keys},
        "definition": definition,
        "media_types": list(row["media_types"] or []),
        "enable_search": row["enable_search"],
        "enable_rss": row["enable_rss"],
        "supports_rss": bool(adapter and adapter.supportsRss),
        "trust_tier": row["trust_tier"],
        "is_private": row["is_private"],
        "min_ratio": row["min_ratio"],
        "min_seed_minutes": row["min_seed_minutes"],
        "requests_per_minute": row["requests_per_minute"],
        "min_interval_seconds": row["min_interval_seconds"],
        "last_test_at": row["last_test_at"].isoformat() if row["last_test_at"] else None,
        "last_test_ok": row["last_test_ok"],
        "last_test_message": row["last_test_message"],
        "health": {**health, "status": _healthStatus(row, health)},
        "site_key": f"custom:{row['id']}",
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


async def _fetch(conn, indexerId: int):
    row = await conn.fetchrow("SELECT * FROM custom_indexers WHERE id = $1", indexerId)
    if not row:
        raise HTTPException(status_code=404, detail="Indexer not found")
    return row


@router.get("/")
async def list_indexers(
    current_user=Depends(require_permission("system.settings")),
    conn: asyncpg.Connection = Depends(get_db),
):
    rows = await conn.fetch("SELECT * FROM custom_indexers ORDER BY lower(name)")
    return [await _toOut(row) for row in rows]


@router.get("/kinds")
async def list_kinds(current_user=Depends(require_permission("system.settings"))):
    """Every adapter with the fields its form shows."""
    return [
        {
            "kind": adapter.kind,
            "label": adapter.label,
            "description": adapter.description,
            "supports_rss": adapter.supportsRss,
            "default_categories": adapter.defaultCategories,
            "settings": [spec.toDict() for spec in adapter.settingFields()],
            "credentials": [spec.toDict() for spec in adapter.credentialFields()],
        }
        for adapter in registry.ADAPTERS.values()
    ]


@router.get("/templates")
async def list_templates(current_user=Depends(require_permission("system.settings"))):
    """Example definitions to start from. They are documentation and are never searched."""
    return TEMPLATES


@router.post("/validate-definition")
async def check_definition(body: DefinitionCheck, current_user=Depends(require_permission("system.settings"))):
    """Every problem with a definition, without saving it."""
    try:
        definition = body.definition if isinstance(body.definition, dict) else parseDefinitionText(body.definition)
    except DefinitionError as e:
        return {"valid": False, "errors": e.errors, "credentials": []}
    errors = validateDefinition(definition)
    return {
        "valid": not errors,
        "errors": errors,
        "credentials": (
            [{"key": key, "label": label} for key, label in credentialLabels(definition)] if not errors else []
        ),
    }


@router.get("/names")
async def list_indexer_names(media_type: Optional[str] = Query(None), current_user=Depends(get_current_user)):
    """Names and trust tiers of the indexers enabled for search, for a media type when one is given."""
    await registry.ensureLoaded()
    indexers = (
        registry.searchIndexers(scopeFor(media_type))
        if media_type
        else [i for i in registry.allIndexers() if i.config.enableSearch]
    )
    return [
        {"name": i.name, "kind": i.kind, "trust_tier": i.config.trustTier, "media_types": i.config.mediaTypes}
        for i in indexers
    ]


@router.post("/test")
async def test_unsaved_indexer(
    body: UnsavedTestRequest,
    current_user=Depends(require_permission("system.settings")),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Test a configuration before it is saved. Masked credentials are filled in from the saved indexer."""
    existing = await _fetch(conn, body.id) if body.id else None
    values = await _prepare(conn, body, existing)
    config = IndexerConfig(
        id=existing["id"] if existing else 0,
        name=values["name"],
        kind=values["kind"],
        baseUrl=values["base_url"],
        settings=values["settings"],
        credentials=values["credentialsPlain"],
        definition=values["definition"],
        mediaTypes=values["media_types"],
        enableSearch=values["enable_search"],
        enableRss=True,
        trustTier=values["trust_tier"],
        isPrivate=values["is_private"],
        minIntervalSeconds=values["min_interval_seconds"],
        requestsPerMinute=values["requests_per_minute"],
    )
    indexer = registry.buildIndexer(config)
    try:
        return await indexer.runTest(body.query, scopeFor(body.test_media_type) if body.test_media_type else None)
    finally:
        close = getattr(indexer, "close", None)
        if close is not None:
            await close()


@router.get("/{indexer_id}")
async def get_indexer(
    indexer_id: int,
    current_user=Depends(require_permission("system.settings")),
    conn: asyncpg.Connection = Depends(get_db),
):
    return await _toOut(await _fetch(conn, indexer_id))


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_indexer(
    body: IndexerWrite,
    current_user=Depends(require_permission("system.settings")),
    conn: asyncpg.Connection = Depends(get_db),
):
    values = await _prepare(conn, body, None)
    async with conn.transaction():
        row = await conn.fetchrow(
            """
            INSERT INTO custom_indexers (
                name, kind, base_url, settings, credentials, definition, media_types,
                enable_search, enable_rss, trust_tier, is_private, min_ratio, min_seed_minutes,
                requests_per_minute, min_interval_seconds
            )
            VALUES ($1, $2, $3, $4::jsonb, $5, $6::jsonb, $7, $8, $9, $10, $11, $12, $13, $14, $15)
            RETURNING *
            """,
            values["name"],
            values["kind"],
            values["base_url"],
            values["settings"],
            values["credentials"],
            values["definition"],
            values["media_types"],
            values["enable_search"],
            values["enable_rss"],
            values["trust_tier"],
            values["is_private"],
            values["min_ratio"],
            values["min_seed_minutes"],
            values["requests_per_minute"],
            values["min_interval_seconds"],
        )
        await _syncSeedRule(conn, values["name"], values["min_ratio"], values["min_seed_minutes"])
        await _syncProfileIndexers(conn, None, values["name"], [], values["media_types"])
    await registry.notifyChanged()
    return await _toOut(row)


@router.put("/{indexer_id}")
async def update_indexer(
    indexer_id: int,
    body: IndexerWrite,
    current_user=Depends(require_permission("system.settings")),
    conn: asyncpg.Connection = Depends(get_db),
):
    existing = await _fetch(conn, indexer_id)
    values = await _prepare(conn, body, existing)
    async with conn.transaction():
        row = await conn.fetchrow(
            """
            UPDATE custom_indexers SET
                name = $2, kind = $3, base_url = $4, settings = $5::jsonb, credentials = $6,
                definition = $7::jsonb, media_types = $8, enable_search = $9, enable_rss = $10,
                trust_tier = $11, is_private = $12, min_ratio = $13, min_seed_minutes = $14,
                requests_per_minute = $15, min_interval_seconds = $16, updated_at = NOW()
            WHERE id = $1
            RETURNING *
            """,
            indexer_id,
            values["name"],
            values["kind"],
            values["base_url"],
            values["settings"],
            values["credentials"],
            values["definition"],
            values["media_types"],
            values["enable_search"],
            values["enable_rss"],
            values["trust_tier"],
            values["is_private"],
            values["min_ratio"],
            values["min_seed_minutes"],
            values["requests_per_minute"],
            values["min_interval_seconds"],
        )
        await _syncSeedRule(conn, values["name"], values["min_ratio"], values["min_seed_minutes"])
        await _syncProfileIndexers(
            conn, existing["name"], values["name"], list(existing["media_types"] or []), values["media_types"]
        )
    await registry.notifyChanged()
    return await _toOut(row)


@router.patch("/{indexer_id}/toggles")
async def toggle_indexer(
    indexer_id: int,
    body: IndexerToggles,
    current_user=Depends(require_permission("system.settings")),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Turn search or RSS monitoring on or off without resending the whole indexer."""
    existing = await _fetch(conn, indexer_id)
    adapter = registry.ADAPTERS.get(existing["kind"])
    if body.enable_rss and not (adapter and adapter.supportsRss):
        raise _invalid(f"{adapter.label if adapter else existing['kind']} indexers have no feed for RSS monitoring")
    row = await conn.fetchrow(
        """
        UPDATE custom_indexers SET
            enable_search = COALESCE($2, enable_search),
            enable_rss = COALESCE($3, enable_rss),
            updated_at = NOW()
        WHERE id = $1
        RETURNING *
        """,
        indexer_id,
        body.enable_search,
        body.enable_rss,
    )
    await registry.notifyChanged()
    return await _toOut(row)


@router.delete("/{indexer_id}")
async def delete_indexer(
    indexer_id: int,
    current_user=Depends(require_permission("system.settings")),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Delete an indexer. Torrents already downloaded from it are not touched, and its
    seeding rule stays so they keep their hit-and-run protection.
    """
    existing = await _fetch(conn, indexer_id)
    async with conn.transaction():
        await conn.execute("DELETE FROM custom_indexers WHERE id = $1", indexer_id)
        await _syncProfileIndexers(conn, existing["name"], None, list(existing["media_types"] or []), [])
    await registry.notifyChanged()
    return {"success": True}


@router.post("/{indexer_id}/test")
async def test_indexer(
    indexer_id: int,
    body: TestRequest,
    current_user=Depends(require_permission("system.settings")),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Run the capability check and a sample search on a saved indexer, and record the outcome."""
    row = await _fetch(conn, indexer_id)
    await registry.ensureLoaded(force=True)
    indexer = registry.byId(indexer_id)
    if indexer is None:
        raise _invalid("The indexer could not be loaded. Check its configuration and save it again")
    result = await indexer.runTest(body.query, scopeFor(body.media_type) if body.media_type else None)
    message = None if result["ok"] else (result.get("error") or {}).get("message")
    await conn.execute(
        "UPDATE custom_indexers SET last_test_at = $2, last_test_ok = $3, last_test_message = $4 WHERE id = $1",
        indexer_id,
        datetime.now(timezone.utc).replace(tzinfo=None),
        result["ok"],
        message,
    )
    if result["ok"]:
        await indexer_health.record_success(row["name"])
    return result
