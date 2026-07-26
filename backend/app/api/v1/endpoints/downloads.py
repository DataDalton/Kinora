"""
Download client monitoring and control endpoints.

Exposes the live qBittorrent state (merged with Kinora download history), per-torrent
controls (pause/resume/delete/recheck/reannounce/force-start/super-seed/sequential/queue),
share- and speed-limit management, and global transfer stats.
"""
import logging
from typing import List, Optional, Dict, Any
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
import asyncpg

from app.db import get_db
from app.services.download_clients.qbittorrent import get_qbittorrent_client
from app.services.download_clients.base import TorrentInfo, TorrentState
from app.api.v1.endpoints.auth import get_current_user, require_permission
from app.schemas.user import User, UserWithPermissions

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------
class ToggleRequest(BaseModel):
    enabled: bool


class QueueActionRequest(BaseModel):
    action: str = Field(..., pattern="^(top|bottom|up|down)$")


class ShareLimitsRequest(BaseModel):
    ratio_limit: float = -1.0
    seeding_time_limit: int = -1
    inactive_seeding_time_limit: int = -1


class SpeedLimitsRequest(BaseModel):
    download_limit: int = Field(0, ge=0)  # bytes/s, 0 = unlimited
    upload_limit: int = Field(0, ge=0)


class AddTorrentRequest(BaseModel):
    url: str  # magnet link or .torrent URL
    media_type: Optional[str] = None
    media_id: Optional[int] = None
    category: Optional[str] = None
    save_path: Optional[str] = None
    tags: Optional[List[str]] = None


class ValidatePreviewRequest(BaseModel):
    media_type: str
    media_id: Optional[int] = None
    profile_id: Optional[int] = None
    files: Optional[List[Dict[str, Any]]] = None  # [{name, size}] for a dry-run report


_PROFILE_TABLE_MAP = {
    "movie": "movies",
    "show": "shows",
    "anime": "anime",
    "album": "albums",
    "music": "albums",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _serialize_torrent(torrent: TorrentInfo) -> Dict[str, Any]:
    """Convert a TorrentInfo dataclass into a JSON-friendly dict."""
    data = asdict(torrent)
    data["state"] = (
        torrent.state.value if isinstance(torrent.state, TorrentState) else torrent.state
    )
    return data


async def _get_client_or_503():
    """Return the qBittorrent client or raise a 503 when not configured."""
    client = await get_qbittorrent_client()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Download client not configured or unavailable",
        )
    return client


def _group_for_state(state: str) -> str:
    """Bucket a torrent state into a UI group."""
    if state == TorrentState.DOWNLOADING.value:
        return "downloading"
    if state == TorrentState.SEEDING.value:
        return "seeding"
    if state in (TorrentState.PAUSED.value, TorrentState.ERROR.value):
        return "paused"
    return "queued"


# ---------------------------------------------------------------------------
# Read endpoints (any authenticated user)
# ---------------------------------------------------------------------------
@router.get("/torrents")
async def list_torrents(
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    List all torrents in the download client, merged with Kinora download history
    so each entry carries media context and validation state.
    """
    client = await get_qbittorrent_client()
    if not client:
        return {"configured": False, "torrents": []}

    try:
        torrents = await client.get_torrents()
    except Exception as exc:
        # Configured but currently unreachable: report it so the page shows a
        # transient error instead of the misleading "not configured" state.
        logger.warning("qBittorrent unreachable while listing torrents: %s", exc)
        return {"configured": True, "unreachable": True, "torrents": []}

    hashes = [t.hash for t in torrents]

    history_map: Dict[str, Dict[str, Any]] = {}
    if hashes:
        rows = await conn.fetch(
            "SELECT * FROM download_history WHERE torrent_hash = ANY($1)", hashes
        )
        history_map = {row["torrent_hash"]: dict(row) for row in rows}

    result = []
    for torrent in torrents:
        entry = _serialize_torrent(torrent)
        entry["group"] = _group_for_state(entry["state"])
        history = history_map.get(torrent.hash)
        if history:
            entry["media_id"] = history.get("media_id")
            entry["media_type"] = history.get("media_type")
            entry["media_title"] = history.get("torrent_title")
            entry["indexer"] = history.get("indexer")
            entry["quality"] = history.get("quality")
            entry["download_status"] = history.get("status")
            entry["validation_step"] = history.get("validation_step")
            entry["validation_report"] = history.get("validation_report")
        else:
            entry["media_id"] = None
            entry["media_type"] = None
            entry["media_title"] = None
            entry["indexer"] = None
            entry["quality"] = None
            entry["download_status"] = None
            entry["validation_step"] = None
            entry["validation_report"] = None
        result.append(entry)

    return {"configured": True, "torrents": result}


@router.get("/stats")
async def get_download_stats(
    current_user: User = Depends(get_current_user),
):
    """Aggregate live stats for the download client (speeds, totals, group counts)."""
    client = await get_qbittorrent_client()
    if not client:
        return {"configured": False}

    try:
        torrents = await client.get_torrents()
        transfer = await client.get_transfer_info()
    except Exception as exc:
        logger.warning("qBittorrent unreachable while fetching stats: %s", exc)
        return {"configured": True, "unreachable": True}

    counts = {"downloading": 0, "seeding": 0, "paused": 0, "queued": 0, "total": len(torrents)}
    for torrent in torrents:
        counts[_group_for_state(torrent.state.value)] += 1

    return {
        "configured": True,
        "download_speed": transfer.get("dl_info_speed", 0),
        "upload_speed": transfer.get("up_info_speed", 0),
        "download_session_total": transfer.get("dl_info_data", 0),
        "upload_session_total": transfer.get("up_info_data", 0),
        "download_rate_limit": transfer.get("dl_rate_limit", 0),
        "upload_rate_limit": transfer.get("up_rate_limit", 0),
        "alt_speed_enabled": bool(transfer.get("use_alt_speed_limits", False)),
        "connection_status": transfer.get("connection_status", "unknown"),
        "dht_nodes": transfer.get("dht_nodes", 0),
        "counts": counts,
    }


@router.get("/history-stats")
async def history_stats(
    hours: int = Query(24, ge=1, le=720),
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Time-bucketed bandwidth/ratio history for the last N hours."""
    from app.services.transfer_stats import get_transfer_history

    return await get_transfer_history(conn, hours)


@router.post("/validate-preview")
async def validate_preview(
    body: ValidatePreviewRequest,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Preview the validation rules (and optionally a dry-run report against a supplied
    file list) that would apply to a release, based on the media item's profile.
    """
    from app.services.media_profile import MediaProfile
    from app.services.torrent_validator import torrent_validator, report_to_dict

    profile_row = None
    if body.profile_id:
        profile_row = await conn.fetchrow(
            "SELECT * FROM media_profiles WHERE id = $1", body.profile_id
        )
    elif body.media_id:
        table = _PROFILE_TABLE_MAP.get(body.media_type)
        if table:
            media = await conn.fetchrow(
                f"SELECT media_profile_id FROM {table} WHERE id = $1", body.media_id
            )
            if media and media.get("media_profile_id"):
                profile_row = await conn.fetchrow(
                    "SELECT * FROM media_profiles WHERE id = $1", media["media_profile_id"]
                )

    if profile_row:
        profile = MediaProfile.from_row(dict(profile_row))
        allowed = profile.get_allowed_extensions_for_type(body.media_type)
        forbidden = profile.forbidden_extensions or torrent_validator.DEFAULT_FORBIDDEN
        validation_enabled = profile.validation_enabled
        failure_action = profile.validation_failure_action
    else:
        allowed = torrent_validator.DEFAULT_ALLOWED.get(body.media_type, [])
        forbidden = torrent_validator.DEFAULT_FORBIDDEN
        validation_enabled = True
        failure_action = "pause_notify"

    result: Dict[str, Any] = {
        "validation_enabled": validation_enabled,
        "failure_action": failure_action,
        "allowed_extensions": allowed,
        "forbidden_extensions": forbidden,
        "report": None,
    }

    if body.files:
        report = torrent_validator.validate_files(
            files=body.files,
            media_type=body.media_type,
            allowed_extensions=allowed,
            forbidden_extensions=forbidden,
        )
        result["report"] = report_to_dict(report)

    return result


@router.get("/torrents/{torrent_hash}")
async def get_torrent_detail(
    torrent_hash: str,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Detailed view for one torrent: live info, files, trackers, and piece states."""
    client = await _get_client_or_503()

    torrent = await client.get_torrent(torrent_hash)
    if not torrent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Torrent not found"
        )

    files = await client.get_torrent_files(torrent_hash)
    trackers = await client.get_torrent_trackers(torrent_hash)
    piece_states = await client.get_piece_states(torrent_hash)

    history = await conn.fetchrow(
        "SELECT * FROM download_history WHERE torrent_hash = $1", torrent_hash
    )

    entry = _serialize_torrent(torrent)
    entry["group"] = _group_for_state(entry["state"])
    entry["files"] = files
    entry["trackers"] = trackers
    entry["piece_states"] = piece_states
    # Always populate the media-context fields so the response matches the
    # TorrentDetail contract, using null where there is no history row.
    history_dict = dict(history) if history else {}
    entry["media_id"] = history_dict.get("media_id")
    entry["media_type"] = history_dict.get("media_type")
    entry["media_title"] = history_dict.get("torrent_title")
    entry["indexer"] = history_dict.get("indexer")
    entry["quality"] = history_dict.get("quality")
    entry["download_status"] = history_dict.get("status")
    entry["validation_step"] = history_dict.get("validation_step")
    entry["validation_report"] = history_dict.get("validation_report")
    return entry


# ---------------------------------------------------------------------------
# Control endpoints (require download-management permission)
# ---------------------------------------------------------------------------
@router.post("/torrents/{torrent_hash}/pause")
async def pause_torrent(
    torrent_hash: str,
    current_user: UserWithPermissions = Depends(require_permission("system.downloads")),
):
    client = await _get_client_or_503()
    await client.pause_torrent(torrent_hash)
    return {"success": True}


@router.post("/torrents/{torrent_hash}/resume")
async def resume_torrent(
    torrent_hash: str,
    current_user: UserWithPermissions = Depends(require_permission("system.downloads")),
):
    client = await _get_client_or_503()
    await client.resume_torrent(torrent_hash)
    return {"success": True}


@router.post("/torrents/{torrent_hash}/recheck")
async def recheck_torrent(
    torrent_hash: str,
    current_user: UserWithPermissions = Depends(require_permission("system.downloads")),
):
    client = await _get_client_or_503()
    await client.recheck_torrent(torrent_hash)
    return {"success": True}


@router.post("/torrents/{torrent_hash}/reannounce")
async def reannounce_torrent(
    torrent_hash: str,
    current_user: UserWithPermissions = Depends(require_permission("system.downloads")),
):
    client = await _get_client_or_503()
    await client.reannounce_torrent(torrent_hash)
    return {"success": True}


@router.post("/torrents/{torrent_hash}/force-start")
async def force_start_torrent(
    torrent_hash: str,
    body: ToggleRequest,
    current_user: UserWithPermissions = Depends(require_permission("system.downloads")),
):
    client = await _get_client_or_503()
    await client.set_force_start(torrent_hash, body.enabled)
    return {"success": True}


@router.post("/torrents/{torrent_hash}/super-seeding")
async def super_seeding_torrent(
    torrent_hash: str,
    body: ToggleRequest,
    current_user: UserWithPermissions = Depends(require_permission("system.downloads")),
):
    client = await _get_client_or_503()
    await client.set_super_seeding(torrent_hash, body.enabled)
    return {"success": True}


@router.post("/torrents/{torrent_hash}/sequential")
async def sequential_torrent(
    torrent_hash: str,
    body: ToggleRequest,
    current_user: UserWithPermissions = Depends(require_permission("system.downloads")),
):
    client = await _get_client_or_503()
    await client.set_sequential_download(torrent_hash, body.enabled)
    return {"success": True}


@router.post("/torrents/{torrent_hash}/queue")
async def queue_torrent(
    torrent_hash: str,
    body: QueueActionRequest,
    current_user: UserWithPermissions = Depends(require_permission("system.downloads")),
):
    client = await _get_client_or_503()
    await client.set_queue_priority(torrent_hash, body.action)
    return {"success": True}


@router.put("/torrents/{torrent_hash}/share-limits")
async def set_torrent_share_limits(
    torrent_hash: str,
    body: ShareLimitsRequest,
    current_user: UserWithPermissions = Depends(require_permission("system.downloads")),
):
    client = await _get_client_or_503()
    await client.set_share_limits(
        torrent_hash,
        ratio_limit=body.ratio_limit,
        seeding_time_limit=body.seeding_time_limit,
        inactive_seeding_time_limit=body.inactive_seeding_time_limit,
    )
    return {"success": True}


@router.put("/torrents/{torrent_hash}/speed-limits")
async def set_torrent_speed_limits(
    torrent_hash: str,
    body: SpeedLimitsRequest,
    current_user: UserWithPermissions = Depends(require_permission("system.downloads")),
):
    client = await _get_client_or_503()
    await client.set_torrent_speed_limits(
        torrent_hash, download_limit=body.download_limit, upload_limit=body.upload_limit
    )
    return {"success": True}


@router.put("/speed-limits")
async def set_global_speed_limits(
    body: SpeedLimitsRequest,
    current_user: UserWithPermissions = Depends(require_permission("system.downloads")),
):
    client = await _get_client_or_503()
    await client.set_global_speed_limits(
        download_limit=body.download_limit, upload_limit=body.upload_limit
    )
    return {"success": True}


@router.post("/alt-speed/toggle")
async def toggle_alt_speed(
    current_user: UserWithPermissions = Depends(require_permission("system.downloads")),
):
    client = await _get_client_or_503()
    await client.toggle_alternative_speed_limits()
    transfer = await client.get_transfer_info()
    return {"success": True, "alt_speed_enabled": bool(transfer.get("use_alt_speed_limits", False))}


@router.delete("/torrents/{torrent_hash}")
async def delete_torrent(
    torrent_hash: str,
    delete_files: bool = Query(False),
    current_user: UserWithPermissions = Depends(require_permission("system.downloads")),
    conn: asyncpg.Connection = Depends(get_db),
):
    client = await _get_client_or_503()
    await client.delete_torrent(torrent_hash, delete_files=delete_files)
    await conn.execute(
        "UPDATE download_history SET status = 'removed', updated_at = NOW() WHERE torrent_hash = $1",
        torrent_hash,
    )
    return {"success": True}


@router.post("/add")
async def add_torrent(
    body: AddTorrentRequest,
    current_user: UserWithPermissions = Depends(require_permission("system.downloads")),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Manually add a magnet or .torrent URL. Optionally maps it to a media item so
    it is tracked in download history like an automated grab.
    """
    client = await _get_client_or_503()

    tags = ["kinora", "manual"] + (body.tags or [])
    torrent_hash = await client.add_torrent(
        torrent=body.url,
        save_path=body.save_path,
        category=body.category or body.media_type,
        tags=tags,
        paused=False,
    )

    # Persist the source so a manually added release can be re-added later. The
    # media_id/media_type columns are required, so the archive row is recorded only
    # when the add is mapped to a media item.
    if body.media_type and body.media_id:
        is_magnet = body.url.strip().startswith("magnet:")
        magnet_link = body.url if is_magnet else None
        torrent_url = None if is_magnet else body.url
        torrent = await client.get_torrent(torrent_hash)
        title = (torrent.name if torrent else None) or body.url
        size = torrent.size if torrent else None
        await conn.execute(
            """
            INSERT INTO download_history (
                torrent_hash, media_type, media_id, torrent_title, indexer,
                size, magnet_link, torrent_url, info_hash, status, progress,
                source, grab_mode, download_client, created_at
            )
            VALUES ($1, $2, $3, $4, 'manual', $5, $6, $7, $8, 'downloading', 0.0, 'manual', 'manual', 'qbittorrent', NOW())
            ON CONFLICT (torrent_hash) DO UPDATE SET
                media_type = EXCLUDED.media_type,
                media_id = EXCLUDED.media_id,
                torrent_title = EXCLUDED.torrent_title,
                magnet_link = COALESCE(EXCLUDED.magnet_link, download_history.magnet_link),
                torrent_url = COALESCE(EXCLUDED.torrent_url, download_history.torrent_url),
                info_hash = COALESCE(EXCLUDED.info_hash, download_history.info_hash),
                updated_at = NOW()
            """,
            torrent_hash,
            body.media_type,
            body.media_id,
            title,
            size,
            magnet_link,
            torrent_url,
            torrent_hash,
        )

    return {"success": True, "hash": torrent_hash}


# ---------------------------------------------------------------------------
# Download-behavior settings (seeding defaults, smart-rule automation, gluetun)
# ---------------------------------------------------------------------------
class AutomationSettings(BaseModel):
    active_peer_pause_enabled: bool = False
    active_peer_pause_minutes: int = 30
    rare_seed_preserve_enabled: bool = False
    rare_seed_threshold: int = 5
    offpeak_enabled: bool = False
    # The off-peak window is the period during which the throttle or pause action applies.
    offpeak_start_hour: int = 0
    offpeak_end_hour: int = 8
    offpeak_action: str = "alt_speed"  # alt_speed | pause
    offpeak_days: List[int] = []  # 0=Mon..6=Sun, empty = every day
    disk_pause_enabled: bool = False
    disk_min_free_gb: int = 10
    disk_min_free_unit: str = "gb"  # gb or percent
    auto_recovery_enabled: bool = False
    stall_timeout_minutes: int = 60
    seed_then_cleanup_enabled: bool = False
    # gluetun ships in the default docker-compose, so integration is on by default
    # and points at the bundled control server. Users on a custom setup can turn it off.
    gluetun_enabled: bool = True
    gluetun_url: str = "http://gluetun:8000"
    vpn_kill_switch_enabled: bool = True
    vpn_port_sync_enabled: bool = True
    # Global and alternative speed limits in KiB/s. 0 means unlimited.
    dl_limit_kbps: int = 0
    up_limit_kbps: int = 0
    alt_dl_limit_kbps: int = 0
    alt_up_limit_kbps: int = 0


class DownloadSettingsUpdate(BaseModel):
    seed_ratio_limit: Optional[float] = None
    seed_time_limit: Optional[int] = None
    inactive_seed_time_limit: Optional[int] = None
    seed_action: str = "pause"
    allow_profile_seed_override: bool = True
    automation: AutomationSettings = AutomationSettings()
    gluetun_api_key: Optional[str] = None  # write-only, omit to keep existing


async def _get_enabled_client_row(conn: asyncpg.Connection):
    return await conn.fetchrow(
        """
        SELECT * FROM download_clients
        WHERE client_type = 'qbittorrent' AND is_enabled = TRUE
        LIMIT 1
        """
    )


def _parse_automation(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, str):
        import json as _json

        try:
            return _json.loads(raw) or {}
        except Exception:
            return {}
    return raw or {}


@router.get("/settings")
async def get_download_settings(
    current_user: UserWithPermissions = Depends(require_permission("system.downloads")),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Return the download client's seeding defaults and automation configuration."""
    row = await _get_enabled_client_row(conn)
    if not row:
        return {"configured": False, "automation": AutomationSettings().model_dump()}

    automation = _parse_automation(row["automation_settings"])
    merged = {**AutomationSettings().model_dump(), **automation}
    # Never return the encrypted gluetun key, expose only whether it is set.
    has_key = bool(merged.pop("gluetun_api_key", None))

    return {
        "configured": True,
        "seed_ratio_limit": row["seed_ratio_limit"],
        "seed_time_limit": row["seed_time_limit"],
        "inactive_seed_time_limit": row["inactive_seed_time_limit"],
        "seed_action": row["seed_action"] or "pause",
        "allow_profile_seed_override": row["allow_profile_seed_override"],
        "automation": merged,
        "gluetun_api_key_set": has_key,
    }


@router.put("/settings")
async def update_download_settings(
    body: DownloadSettingsUpdate,
    current_user: UserWithPermissions = Depends(require_permission("system.downloads")),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Update seeding defaults and automation configuration on the enabled client."""
    from app.api.v1.endpoints.setup import encrypt_value

    row = await _get_enabled_client_row(conn)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No enabled qBittorrent client configured",
        )

    existing_automation = _parse_automation(row["automation_settings"])
    automation = body.automation.model_dump()
    # Preserve the previously stored encrypted gluetun key unless a new one is given.
    if body.gluetun_api_key:
        automation["gluetun_api_key"] = encrypt_value(body.gluetun_api_key)
    elif existing_automation.get("gluetun_api_key"):
        automation["gluetun_api_key"] = existing_automation["gluetun_api_key"]

    await conn.execute(
        """
        UPDATE download_clients
        SET seed_ratio_limit = $1,
            seed_time_limit = $2,
            inactive_seed_time_limit = $3,
            seed_action = $4,
            allow_profile_seed_override = $5,
            automation_settings = $6::jsonb,
            updated_at = NOW()
        WHERE id = $7
        """,
        body.seed_ratio_limit,
        body.seed_time_limit,
        body.inactive_seed_time_limit,
        body.seed_action,
        body.allow_profile_seed_override,
        # The pool registers a jsonb codec, so the dict is passed directly rather
        # than pre-serialized, which would store a double-encoded JSON string.
        automation,
        row["id"],
    )

    # Push the speed limits to qBittorrent. Global limits use bytes/s, the
    # alternative limits are preferences in KiB/s. Best effort so a client
    # that is down does not block saving the settings.
    try:
        client = await get_qbittorrent_client()
        if client:
            await client.set_global_speed_limits(
                body.automation.dl_limit_kbps * 1024,
                body.automation.up_limit_kbps * 1024,
            )
            await client.set_preferences(
                {
                    "alt_dl_limit": body.automation.alt_dl_limit_kbps,
                    "alt_up_limit": body.automation.alt_up_limit_kbps,
                }
            )
    except Exception as exc:
        logger.warning("Failed to apply speed limits to qBittorrent: %s", exc)

    return {"success": True}


# ---------------------------------------------------------------------------
# Per-indexer hit-and-run seed rules
# ---------------------------------------------------------------------------
class IndexerSeedRule(BaseModel):
    indexer: str
    min_ratio: float = 0.0
    min_seed_minutes: int = 0
    enabled: bool = True


@router.get("/indexer-rules")
async def list_indexer_rules(
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    rows = await conn.fetch(
        "SELECT * FROM indexer_seed_rules ORDER BY indexer"
    )
    return [dict(r) for r in rows]


@router.put("/indexer-rules")
async def upsert_indexer_rule(
    body: IndexerSeedRule,
    current_user: UserWithPermissions = Depends(require_permission("system.downloads")),
    conn: asyncpg.Connection = Depends(get_db),
):
    row = await conn.fetchrow(
        """
        INSERT INTO indexer_seed_rules (indexer, min_ratio, min_seed_minutes, enabled)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (indexer) DO UPDATE SET
            min_ratio = EXCLUDED.min_ratio,
            min_seed_minutes = EXCLUDED.min_seed_minutes,
            enabled = EXCLUDED.enabled,
            updated_at = NOW()
        RETURNING *
        """,
        body.indexer,
        body.min_ratio,
        body.min_seed_minutes,
        body.enabled,
    )
    return dict(row)


@router.delete("/indexer-rules/{rule_id}")
async def delete_indexer_rule(
    rule_id: int,
    current_user: UserWithPermissions = Depends(require_permission("system.downloads")),
    conn: asyncpg.Connection = Depends(get_db),
):
    await conn.execute("DELETE FROM indexer_seed_rules WHERE id = $1", rule_id)
    return {"success": True}


# ---------------------------------------------------------------------------
# Manual import queue
# ---------------------------------------------------------------------------
class ResolveImportRequest(BaseModel):
    media_id: Optional[int] = None
    season_number: Optional[int] = None
    episode_number: Optional[int] = None


@router.get("/import")
async def list_import_queue(
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """List files awaiting manual import mapping."""
    rows = await conn.fetch(
        "SELECT * FROM import_queue WHERE status = 'pending' ORDER BY created_at DESC"
    )
    return [dict(r) for r in rows]


@router.get("/import/{item_id}/suggest")
async def suggest_import_matches(
    item_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Suggest library items that match a queued file's name."""
    import re

    item = await conn.fetchrow("SELECT * FROM import_queue WHERE id = $1", item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import item not found")

    table = _PROFILE_TABLE_MAP.get(item["media_type"] or "")
    if not table:
        return []

    name = item["torrent_name"] or item["file_path"] or ""
    tokens = [w for w in re.split(r"[^A-Za-z0-9]+", name) if len(w) >= 3][:6]
    if not tokens:
        return []

    conditions = " OR ".join(f"title ILIKE ${i + 1}" for i in range(len(tokens)))
    params = [f"%{t}%" for t in tokens]
    rows = await conn.fetch(
        f"SELECT id, title FROM {table} WHERE {conditions} ORDER BY title LIMIT 8",
        *params,
    )
    return [{"media_id": r["id"], "title": r["title"]} for r in rows]


@router.post("/import/{item_id}/resolve")
async def resolve_import(
    item_id: int,
    body: ResolveImportRequest,
    current_user: UserWithPermissions = Depends(require_permission("system.downloads")),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Map a queued file to a media item (and season/episode) and organize it."""
    from app.services.import_queue import resolve_import_item

    item = await conn.fetchrow("SELECT * FROM import_queue WHERE id = $1", item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import item not found")

    item_dict = dict(item)
    media_id = body.media_id or item_dict.get("media_id")
    if not media_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="A media_id is required"
        )

    try:
        destination = await resolve_import_item(
            conn, item_dict, media_id, body.season_number, body.episode_number
        )
    except Exception as e:
        await conn.execute(
            "UPDATE import_queue SET error_message = $1, updated_at = NOW() WHERE id = $2",
            str(e), item_id,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    await conn.execute(
        """
        UPDATE import_queue
        SET status = 'imported', media_id = $1, season_number = $2, episode_number = $3,
            error_message = NULL, updated_at = NOW()
        WHERE id = $4
        """,
        media_id, body.season_number, body.episode_number, item_id,
    )
    return {"success": True, "destination": destination}


@router.delete("/import/{item_id}")
async def dismiss_import(
    item_id: int,
    current_user: UserWithPermissions = Depends(require_permission("system.downloads")),
    conn: asyncpg.Connection = Depends(get_db),
):
    await conn.execute(
        "UPDATE import_queue SET status = 'dismissed', updated_at = NOW() WHERE id = $1",
        item_id,
    )
    return {"success": True}


# ---------------------------------------------------------------------------
# Source archive (re-add from stored magnet / .torrent)
# ---------------------------------------------------------------------------
@router.get("/sources")
async def list_sources(
    search: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """List downloads with their stored magnet/.torrent sources for re-adding."""
    if search:
        rows = await conn.fetch(
            """
            SELECT id, torrent_title, media_type, media_id, indexer, quality, status,
                   magnet_link, torrent_url, info_hash, indexer_page_url, root_folder_id,
                   torrent_hash, created_at
            FROM download_history
            WHERE (magnet_link IS NOT NULL OR torrent_url IS NOT NULL)
              AND torrent_title ILIKE $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            f"%{search}%", limit,
        )
    else:
        rows = await conn.fetch(
            """
            SELECT id, torrent_title, media_type, media_id, indexer, quality, status,
                   magnet_link, torrent_url, info_hash, indexer_page_url, root_folder_id,
                   torrent_hash, created_at
            FROM download_history
            WHERE magnet_link IS NOT NULL OR torrent_url IS NOT NULL
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit,
        )
    return [dict(r) for r in rows]


@router.post("/sources/{history_id}/re-add")
async def re_add_source(
    history_id: int,
    current_user: UserWithPermissions = Depends(require_permission("system.downloads")),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Re-add a previously grabbed release from its stored magnet or .torrent URL."""
    from app.services.folder_selector import folderSelector

    row = await conn.fetchrow(
        "SELECT * FROM download_history WHERE id = $1", history_id
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

    source = row["torrent_url"] or row["magnet_link"]
    if not source:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No stored magnet or torrent URL"
        )

    client = await _get_client_or_503()

    save_path = None
    if row.get("root_folder_id"):
        folder = await folderSelector.getFolder(conn, row["root_folder_id"])
        if folder:
            save_path = folder["download_path"]

    # The stored info hash (or prior torrent hash) identifies the same torrent, so
    # it is used directly instead of re-interrogating qBittorrent after adding.
    torrent_hash = await client.add_torrent(
        torrent=source,
        save_path=save_path,
        category=row["media_type"],
        tags=["kinora", "re-add", row["indexer"]] if row["indexer"] else ["kinora", "re-add"],
        paused=False,
        known_hash=row.get("info_hash") or row.get("torrent_hash"),
    )

    await conn.execute(
        "UPDATE download_history SET status = 'downloading', torrent_hash = $1, progress = 0.0, updated_at = NOW() WHERE id = $2",
        torrent_hash, history_id,
    )
    return {"success": True, "hash": torrent_hash}


# ---------------------------------------------------------------------------
# Connection safety, gluetun control, and interface binding
# ---------------------------------------------------------------------------
_PRIVATE_HOSTS = ("localhost", "127.0.0.1", "qbittorrent", "gluetun")


def _is_private_host(host: str) -> bool:
    if not host:
        return False
    if host in _PRIVATE_HOSTS:
        return True
    return host.startswith("192.168.") or host.startswith("10.") or host.startswith("172.")


@router.get("/connection-safety")
async def connection_safety(
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Report VPN connection safety, authoritatively via gluetun when configured."""
    from app.services.gluetun import get_gluetun_client, get_kinora_public_ip

    kinora_ip = await get_kinora_public_ip()
    gluetun = await get_gluetun_client()

    # qBittorrent's interface binding, read once and reported in both modes so the UI can
    # show whether the client is pinned to the VPN tunnel as a kill switch.
    client = await get_qbittorrent_client()
    iface = ""
    iface_addr = ""
    if client:
        try:
            prefs = await client.get_preferences()
            iface = prefs.get("current_network_interface") or ""
            iface_addr = prefs.get("current_interface_address") or ""
        except Exception:
            iface = ""
            iface_addr = ""

    if gluetun:
        pub = await gluetun.get_public_ip()
        vpn_status = await gluetun.get_vpn_status()
        forwarded_port = await gluetun.get_forwarded_port()
        vpn_up = vpn_status == "running"
        client_ip = pub.get("public_ip") if pub else None
        country = pub.get("country") if pub else None
        city = pub.get("city") if pub else None
        provider = (pub.get("organization") or pub.get("provider")) if pub else None

        if not vpn_up:
            severity, message = "error", "VPN tunnel is not running"
        elif client_ip and kinora_ip and client_ip == kinora_ip:
            severity, message = "error", "Torrent traffic is exiting on Kinora's IP (VPN leak)"
        elif not client_ip:
            severity, message = "warn", "Could not read the VPN public IP"
        else:
            severity, message = "ok", f"VPN active{f' via {provider}' if provider else ''}"

        return {
            "configured": True,
            "source": "gluetun",
            "severity": severity,
            "message": message,
            "kinora_public_ip": kinora_ip,
            "client_public_ip": client_ip,
            "country": country,
            "city": city,
            "provider": provider,
            "vpn_up": vpn_up,
            "forwarded_port": forwarded_port,
            "interface_bound": bool(iface),
            "client_interface": iface,
            "client_interface_address": iface_addr,
        }

    # Heuristic fallback via qBittorrent interface binding.
    if not client:
        return {
            "configured": False,
            "source": "none",
            "severity": "warn",
            "message": "Download client not configured",
            "kinora_public_ip": kinora_ip,
        }

    bound = bool(iface)

    row = await _get_enabled_client_row(conn)
    same_host = _is_private_host(row["host"]) if row else False

    if not bound:
        severity = "warn"
        message = (
            "qBittorrent is not bound to a specific interface, so a VPN drop would not "
            "stop torrent traffic."
        )
        if same_host:
            message += " The client is also on Kinora's network."
    else:
        severity = "ok"
        message = f"qBittorrent is bound to interface '{iface}'"

    return {
        "configured": True,
        "source": "heuristic",
        "severity": severity,
        "message": message,
        "kinora_public_ip": kinora_ip,
        "interface_bound": bound,
        "client_interface": iface,
        "client_interface_address": iface_addr,
    }


@router.get("/gluetun")
async def gluetun_status(
    current_user: User = Depends(get_current_user),
):
    """Return gluetun tunnel status, public IP/location, forwarded port, and version."""
    from app.services.gluetun import get_gluetun_client

    gluetun = await get_gluetun_client()
    if not gluetun:
        return {"configured": False}

    pub = await gluetun.get_public_ip()
    vpn_status = await gluetun.get_vpn_status()
    forwarded_port = await gluetun.get_forwarded_port()
    version = await gluetun.get_version()

    return {
        "configured": True,
        # Raw control-server status. None means the control server could not be reached;
        # a string like "stopped"/"crashed" means gluetun answered but the tunnel is down.
        "reachable": vpn_status is not None,
        "vpn_status": vpn_status,
        "running": vpn_status == "running",
        "public_ip": pub.get("public_ip") if pub else None,
        "country": pub.get("country") if pub else None,
        "city": pub.get("city") if pub else None,
        "provider": (pub.get("organization") or pub.get("provider")) if pub else None,
        "forwarded_port": forwarded_port,
        "version": version,
    }


@router.post("/gluetun/sync-port")
async def gluetun_sync_port(
    current_user: UserWithPermissions = Depends(require_permission("system.downloads")),
):
    """Sync qBittorrent's listen port to the VPN's forwarded port."""
    from app.services.gluetun import get_gluetun_client

    gluetun = await get_gluetun_client()
    if not gluetun:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Gluetun not configured")

    port = await gluetun.get_forwarded_port()
    if not port:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No forwarded port available")

    client = await _get_client_or_503()
    await client.set_preferences({"listen_port": port})
    return {"success": True, "port": port}


@router.post("/gluetun/{action}")
async def gluetun_control(
    action: str,
    current_user: UserWithPermissions = Depends(require_permission("system.downloads")),
):
    """Control the VPN tunnel. action: 'restart' (reconnect / rotate server) | 'stop' | 'start'."""
    from app.services.gluetun import get_gluetun_client

    if action not in ("restart", "stop", "start"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid action")

    gluetun = await get_gluetun_client()
    if not gluetun:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Gluetun not configured")

    if action == "stop":
        await gluetun.set_vpn_status("stopped")
    elif action == "start":
        await gluetun.set_vpn_status("running")
    else:  # restart: stop then start forces a reconnect to a new server in the pool
        await gluetun.set_vpn_status("stopped")
        await gluetun.set_vpn_status("running")

    return {"success": True}


@router.get("/interfaces")
async def list_network_interfaces(
    current_user: UserWithPermissions = Depends(require_permission("system.downloads")),
):
    """List network interfaces qBittorrent can bind to (defense-in-depth kill switch)."""
    client = await _get_client_or_503()
    return await client.get_network_interfaces()


class InterfaceBindingRequest(BaseModel):
    interface: str
    address: str = ""


@router.post("/interface-binding")
async def set_interface_binding(
    body: InterfaceBindingRequest,
    current_user: UserWithPermissions = Depends(require_permission("system.downloads")),
):
    """Bind qBittorrent to a network interface (e.g. the VPN tunnel) as a kill switch."""
    client = await _get_client_or_503()
    prefs: Dict[str, Any] = {"current_network_interface": body.interface}
    if body.address:
        prefs["current_interface_address"] = body.address
    await client.set_preferences(prefs)
    return {"success": True}
