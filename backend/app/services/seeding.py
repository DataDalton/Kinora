"""
Seeding limit resolution and application.

Implements the 3-tier cascade: global download-client defaults are overridden by
per-media-profile values (when the client allows overrides), which are overridden
by per-torrent manual settings on the downloads page.

Values use qBittorrent share-limit sentinels: -1 = use client/global limit,
-2 = unlimited. Times are in minutes.
"""

from typing import Optional, Tuple, Dict, Any, TYPE_CHECKING
import logging

from app.db import get_pool

if TYPE_CHECKING:
    from app.services.download_clients.qbittorrent import QBittorrentClient
    from app.services.media_profile import MediaProfile

logger = logging.getLogger(__name__)

# qBittorrent max_ratio_act values for the action taken when a share limit is reached.
SEED_ACTION_MAP = {
    "pause": 0,
    "remove": 1,
    "remove_delete": 3,
}


async def get_global_seed_defaults() -> Dict[str, Any]:
    """
    Load the global seeding defaults and automation settings from the enabled
    download client. Returns sentinel-friendly defaults when unset.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT seed_ratio_limit, seed_time_limit, inactive_seed_time_limit,
                   seed_action, allow_profile_seed_override, automation_settings
            FROM download_clients
            WHERE client_type = 'qbittorrent' AND is_enabled = TRUE
            LIMIT 1
            """)

    if not row:
        return {
            "ratio": None,
            "time": None,
            "inactive": None,
            "action": "pause",
            "allow_override": True,
            "automation": {},
        }

    automation = row["automation_settings"]
    if isinstance(automation, str):
        import json

        try:
            automation = json.loads(automation)
        except Exception:
            automation = {}

    return {
        "ratio": row["seed_ratio_limit"],
        "time": row["seed_time_limit"],
        "inactive": row["inactive_seed_time_limit"],
        "action": row["seed_action"] or "pause",
        "allow_override": row["allow_profile_seed_override"],
        "automation": automation or {},
    }


def resolve_share_limits(
    global_defaults: Dict[str, Any],
    profile: Optional["MediaProfile"],
) -> Tuple[float, int, int]:
    """
    Resolve effective (ratio_limit, seeding_time_limit, inactive_seeding_time_limit)
    from global defaults and an optional profile override.

    Precedence: profile value (when overrides allowed) > global default > -1 (client global).
    """
    allow_override = global_defaults.get("allow_override", True)

    def pick(profile_value: Optional[float], global_value: Optional[float]) -> float:
        if allow_override and profile_value is not None:
            return profile_value
        if global_value is not None:
            return global_value
        return -1

    ratio = pick(
        getattr(profile, "seed_ratio_limit", None) if profile else None,
        global_defaults.get("ratio"),
    )
    seeding_time = int(
        pick(
            getattr(profile, "seed_time_limit", None) if profile else None,
            global_defaults.get("time"),
        )
    )
    inactive = int(
        pick(
            getattr(profile, "inactive_seed_time_limit", None) if profile else None,
            global_defaults.get("inactive"),
        )
    )
    return ratio, seeding_time, inactive


async def apply_seeding_limits(
    client: "QBittorrentClient",
    torrent_hash: str,
    profile: Optional["MediaProfile"] = None,
) -> None:
    """
    Resolve and apply seeding limits to a torrent, and ensure the client's global
    share-limit action matches the configured seed action. Failures are logged and
    swallowed so they never block a download.
    """
    try:
        defaults = await get_global_seed_defaults()

        # Set the global action (pause/remove/remove+delete) once per apply.
        action = defaults.get("action", "pause")
        act_value = SEED_ACTION_MAP.get(action)
        if act_value is not None:
            try:
                await client.set_preferences({"max_ratio_act": act_value})
            except Exception as e:
                logger.debug(f"Could not set max_ratio_act: {e}")

        ratio, seeding_time, inactive = resolve_share_limits(defaults, profile)

        # Only send share limits when at least one is an explicit (non-global) value.
        if ratio == -1 and seeding_time == -1 and inactive == -1:
            return

        await client.set_share_limits(
            torrent_hash,
            ratio_limit=ratio,
            seeding_time_limit=seeding_time,
            inactive_seeding_time_limit=inactive,
        )
        logger.info(
            f"Applied seeding limits to {torrent_hash[:8]}: " f"ratio={ratio} time={seeding_time} inactive={inactive}"
        )
    except Exception as e:
        logger.warning(f"Failed to apply seeding limits to {torrent_hash[:8]}: {e}")
