"""
Smart seeding and reliability rules engine.

Evaluated once per cycle by the seeding-monitor Celery task. Applies:
- Active-peer-aware seeding (pause when idle, resume when peers return)
- Rare-torrent preservation (keep seeding scarce content)
- Per-indexer hit-and-run protection (never stop before tracker minimums)
- Off-peak scheduling (pause or throttle outside configured hours/days)
- Seed-then-cleanup (remove torrents once goals and tracker minimums are met; opt-in)
- Disk-space-aware pausing (pause downloads when free space is low; never deletes)
- Stalled/failed auto-recovery (blocklist and re-queue the media item; opt-in)
- VPN kill switch + forwarded-port sync + drift notifications

Per-torrent rule timers live in the durable torrent_rule_state table (not the
cache) so countdowns survive restarts. Torrents auto-paused by a rule are tagged
so only rule-paused torrents are auto-resumed, never user-paused ones.
"""

import shutil
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple

from app.db import get_pool
from app.core.config import settings
from app.services.download_clients.qbittorrent import get_qbittorrent_client
from app.services.download_clients.base import TorrentState
from app.services.seeding import get_global_seed_defaults
from app.services.notifications import (
    create_notification,
    SEVERITY_ERROR,
    SEVERITY_SUCCESS,
    SEVERITY_WARNING,
    SEVERITY_INFO,
)

logger = logging.getLogger(__name__)

AUTOPAUSE_TAG = "kinora-autopause"
VPNKILL_TAG = "kinora-vpnkill"

_MEDIA_TABLES = {
    "movie": "movies",
    "show": "shows",
    "anime": "anime",
    "album": "albums",
    "music": "albums",
}


def hour_in_window(hour: int, start: int, end: int) -> bool:
    """Whether an hour falls inside a [start, end) window that may wrap midnight."""
    if start == end:
        return True
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def goal_met(torrent) -> bool:
    """Whether a torrent has reached its own configured ratio or seeding-time limit."""
    if torrent.ratio_limit is not None and torrent.ratio_limit > 0 and torrent.ratio >= torrent.ratio_limit:
        return True
    if (
        torrent.seeding_time_limit is not None
        and torrent.seeding_time_limit > 0
        and torrent.seeding_time >= torrent.seeding_time_limit * 60
    ):
        return True
    return False


class SeedingRulesEngine:
    def __init__(self):
        self._flag_cache: Dict[Tuple[str, int], Tuple[bool, Optional[bool]]] = {}

    async def run(self) -> Dict[str, Any]:
        self._flag_cache.clear()
        client = await get_qbittorrent_client()
        if not client:
            return {"status": "skipped", "reason": "qBittorrent not configured"}

        defaults = await get_global_seed_defaults()
        automation = defaults.get("automation", {})

        # VPN kill switch and forwarded-port sync run first, before per-torrent rules.
        await self._apply_vpn_safety(client, automation)

        torrents = await client.get_torrents()
        if not torrents:
            return {"status": "success", "evaluated": 0}

        pool = await get_pool()
        async with pool.acquire() as conn:
            hashes = [t.hash for t in torrents]
            history_map = await self._load_history(conn, hashes)
            indexer_rules = await self._load_indexer_rules(conn)
            rule_states = await self._load_rule_states(conn, hashes)

            # Local wall-clock time so the off-peak window and day-of-week honor the
            # server timezone (TZ env), matching what the settings UI states. Rule
            # timers use elapsed differences, so the timezone choice does not affect them.
            now_dt = datetime.now()
            hour = now_dt.hour
            weekday = now_dt.weekday()  # 0 = Monday

            # Global off-peak alternative-speed handling (once per cycle).
            await self._apply_offpeak_alt_speed(client, automation, hour, weekday)

            disk_low = self._check_disk_low(automation)

            actions = {"paused": 0, "resumed": 0, "cleaned": 0, "recovered": 0}

            for torrent in torrents:
                ctx = history_map.get(torrent.hash)
                try:
                    await self._evaluate(
                        conn,
                        client,
                        torrent,
                        ctx,
                        automation,
                        indexer_rules,
                        rule_states,
                        now_dt,
                        hour,
                        weekday,
                        disk_low,
                        actions,
                    )
                except Exception as e:
                    logger.warning(f"Seeding rule error for {torrent.hash[:8]}: {e}")

            # Prune rule-state rows for torrents no longer present.
            await conn.execute("DELETE FROM torrent_rule_state WHERE torrent_hash <> ALL($1)", hashes)

        return {"status": "success", "evaluated": len(torrents), **actions}

    # ------------------------------------------------------------------
    # VPN safety
    # ------------------------------------------------------------------
    async def _apply_vpn_safety(self, client, automation: Dict[str, Any]) -> None:
        """Sync the VPN forwarded port and enforce the kill switch when enabled."""
        if not automation.get("vpn_port_sync_enabled") and not automation.get("vpn_kill_switch_enabled"):
            return
        try:
            from app.services.gluetun import get_gluetun_client, get_kinora_public_ip

            gluetun = await get_gluetun_client()
            if not gluetun:
                return

            if automation.get("vpn_port_sync_enabled"):
                await self._sync_forwarded_port(client, gluetun)

            if automation.get("vpn_kill_switch_enabled"):
                vpn_status = await gluetun.get_vpn_status()
                pub = await gluetun.get_public_ip()
                client_ip = pub.get("public_ip") if pub else None
                kinora_ip = await get_kinora_public_ip()
                leak = (vpn_status != "running") or bool(client_ip and kinora_ip and client_ip == kinora_ip)
                await self._enforce_kill_switch(client, leak)
        except Exception as e:
            logger.warning(f"VPN safety check failed: {e}")

    async def _sync_forwarded_port(self, client, gluetun) -> None:
        """Match qBittorrent's listen port to the VPN forwarded port, notify on drift."""
        port = await gluetun.get_forwarded_port()
        if not port:
            return
        prefs = await client.get_preferences()
        current = prefs.get("listen_port")
        if current != port:
            await client.set_preferences({"listen_port": port})
            logger.info(f"Synced qBittorrent listen port to VPN forwarded port {port}")
            await create_notification(
                type="port_drift",
                title="VPN forwarded port changed",
                message=f"qBittorrent's listen port was synced to {port}.",
                severity=SEVERITY_INFO,
                data={"port": port, "previous": current},
                dedup_window_seconds=600,
            )

    async def _enforce_kill_switch(self, client, leak: bool) -> None:
        """
        Pause all active torrents on a VPN leak/down, resume when healthy. State is
        derived from a tag (durable) rather than cache, so a cache flush can never
        leave torrents stuck paused.
        """
        torrents = await client.get_torrents()
        tagged = [t for t in torrents if VPNKILL_TAG in (t.tags or [])]

        if leak:
            paused = 0
            for t in torrents:
                if VPNKILL_TAG not in (t.tags or []) and t.state in (
                    TorrentState.DOWNLOADING,
                    TorrentState.SEEDING,
                    TorrentState.QUEUED,
                ):
                    await client.pause_torrent(t.hash)
                    await client.set_tags(t.hash, [VPNKILL_TAG])
                    paused += 1
            if paused > 0:
                await self._vpn_alert(SEVERITY_ERROR, f"VPN unsafe: paused {paused} torrent(s)")
                await create_notification(
                    type="vpn_killswitch",
                    title="VPN kill switch engaged",
                    message=f"The VPN tunnel is down or leaking. Paused {paused} torrent(s).",
                    severity=SEVERITY_ERROR,
                    dedup_window_seconds=300,
                )
                logger.warning(f"VPN kill switch engaged: paused {paused} torrents")
        elif tagged:
            for t in tagged:
                await client.resume_torrent(t.hash)
                await client.remove_tags(t.hash, [VPNKILL_TAG])
            await self._vpn_alert(SEVERITY_SUCCESS, "VPN restored: resumed paused torrents")
            await create_notification(
                type="vpn_restored",
                title="VPN restored",
                message=f"The VPN tunnel is healthy again. Resumed {len(tagged)} torrent(s).",
                severity=SEVERITY_SUCCESS,
            )
            logger.info("VPN kill switch released: resumed torrents")

    async def _vpn_alert(self, severity: str, message: str) -> None:
        try:
            from app.core.webtransport import webtransport_manager

            for user_id in webtransport_manager.get_active_users():
                await webtransport_manager.send_vpn_alert(user_id, severity, message)
        except Exception as e:
            logger.debug(f"VPN alert push failed: {e}")

    # ------------------------------------------------------------------
    # Loaders
    # ------------------------------------------------------------------
    async def _load_history(self, conn, hashes) -> Dict[str, Dict[str, Any]]:
        if not hashes:
            return {}
        rows = await conn.fetch(
            "SELECT torrent_hash, media_id, media_type, indexer, torrent_title FROM download_history WHERE torrent_hash = ANY($1)",
            hashes,
        )
        return {r["torrent_hash"]: dict(r) for r in rows}

    async def _load_indexer_rules(self, conn) -> Dict[str, Dict[str, Any]]:
        rows = await conn.fetch(
            "SELECT indexer, min_ratio, min_seed_minutes FROM indexer_seed_rules WHERE enabled = TRUE"
        )
        return {
            r["indexer"].lower(): {
                "min_ratio": r["min_ratio"],
                "min_seed_seconds": r["min_seed_minutes"] * 60,
            }
            for r in rows
        }

    async def _load_rule_states(self, conn, hashes) -> Dict[str, Dict[str, Any]]:
        if not hashes:
            return {}
        rows = await conn.fetch(
            "SELECT torrent_hash, no_peers_since, stalled_since FROM torrent_rule_state WHERE torrent_hash = ANY($1)",
            hashes,
        )
        return {
            r["torrent_hash"]: {
                "no_peers_since": r["no_peers_since"],
                "stalled_since": r["stalled_since"],
            }
            for r in rows
        }

    async def _set_timer(self, conn, torrent_hash: str, column: str, value) -> None:
        await conn.execute(
            f"""
            INSERT INTO torrent_rule_state (torrent_hash, {column}, updated_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT (torrent_hash) DO UPDATE SET {column} = $2, updated_at = NOW()
            """,
            torrent_hash,
            value,
        )

    async def _get_media_flags(
        self, conn, media_type: Optional[str], media_id: Optional[int]
    ) -> Tuple[bool, Optional[bool]]:
        """Return (seed_then_cleanup, auto_recovery) profile flags for a media item."""
        if not media_type or not media_id:
            return (False, None)
        key = (media_type, media_id)
        if key in self._flag_cache:
            return self._flag_cache[key]

        table = _MEDIA_TABLES.get(media_type)
        result: Tuple[bool, Optional[bool]] = (False, None)
        if table:
            row = await conn.fetchrow(
                f"""
                SELECT mp.seed_then_cleanup, mp.auto_recovery
                FROM {table} m
                LEFT JOIN media_profiles mp ON m.media_profile_id = mp.id
                WHERE m.id = $1
                """,
                media_id,
            )
            if row:
                result = (bool(row["seed_then_cleanup"]), row["auto_recovery"])
        self._flag_cache[key] = result
        return result

    # ------------------------------------------------------------------
    # Off-peak / disk
    # ------------------------------------------------------------------
    def _offpeak_restrict(self, automation: Dict[str, Any], hour: int, weekday: int) -> bool:
        """True when the current hour is inside the off-peak window, where the throttle
        or pause action applies. The window is defined directly by the user."""
        if not automation.get("offpeak_enabled"):
            return False
        days = automation.get("offpeak_days") or []
        if days and weekday not in days:
            return False  # schedule does not apply today
        return hour_in_window(hour, automation.get("offpeak_start_hour", 0), automation.get("offpeak_end_hour", 8))

    def _check_disk_low(self, automation: Dict[str, Any]) -> bool:
        if not automation.get("disk_pause_enabled"):
            return False
        try:
            downloads_root = getattr(settings, "DOWNLOADS_ROOT", "/downloads")
            usage = shutil.disk_usage(downloads_root)
            threshold = automation.get("disk_min_free_gb", 10)
            if automation.get("disk_min_free_unit", "gb") == "percent":
                free_percent = (usage.free / usage.total) * 100 if usage.total else 100
                return free_percent < threshold
            free_gb = usage.free / (1024**3)
            return free_gb < threshold
        except Exception as e:
            logger.debug(f"Disk-space check failed: {e}")
            return False

    async def _apply_offpeak_alt_speed(self, client, automation, hour, weekday):
        if not automation.get("offpeak_enabled") or automation.get("offpeak_action") != "alt_speed":
            return
        want_alt = self._offpeak_restrict(automation, hour, weekday)
        try:
            transfer = await client.get_transfer_info()
            current_alt = bool(transfer.get("use_alt_speed_limits", False))
            if want_alt != current_alt:
                await client.toggle_alternative_speed_limits()
        except Exception as e:
            logger.debug(f"Off-peak alt-speed toggle failed: {e}")

    # ------------------------------------------------------------------
    # Per-torrent evaluation
    # ------------------------------------------------------------------
    async def _evaluate(
        self,
        conn,
        client,
        torrent,
        ctx,
        automation,
        indexer_rules,
        rule_states,
        now_dt,
        hour,
        weekday,
        disk_low,
        actions,
    ):
        tags = torrent.tags or []
        rule_paused = AUTOPAUSE_TAG in tags
        indexer = (ctx or {}).get("indexer")
        state = rule_states.get(torrent.hash, {})

        seed_then_cleanup, profile_auto_recovery = await self._get_media_flags(
            conn, (ctx or {}).get("media_type"), (ctx or {}).get("media_id")
        )

        # Hit-and-run protection status.
        hr = indexer_rules.get(indexer.lower()) if indexer else None
        hr_met = True
        if hr:
            hr_met = torrent.ratio >= hr["min_ratio"] and torrent.seeding_time >= hr["min_seed_seconds"]

        is_complete = torrent.progress >= 1.0 or torrent.state == TorrentState.SEEDING

        # ---- Downloading torrents: auto-recovery + disk-aware pause ----
        if not is_complete:
            auto_recovery = (
                profile_auto_recovery
                if profile_auto_recovery is not None
                else automation.get("auto_recovery_enabled", False)
            )
            if auto_recovery and await self._handle_stall(conn, client, torrent, ctx, automation, state, now_dt):
                actions["recovered"] += 1
                return

            # Disk-aware pausing of active downloads (pause only, never delete).
            if disk_low and torrent.state == TorrentState.DOWNLOADING and not rule_paused:
                await client.pause_torrent(torrent.hash)
                await client.set_tags(torrent.hash, [AUTOPAUSE_TAG])
                actions["paused"] += 1
            elif not disk_low and rule_paused and torrent.state == TorrentState.PAUSED:
                await client.resume_torrent(torrent.hash)
                await client.remove_tags(torrent.hash, [AUTOPAUSE_TAG])
                actions["resumed"] += 1
            return

        # ---- Complete torrents: preservation, cleanup, pause/resume ----
        protected = not hr_met
        if automation.get("rare_seed_preserve_enabled"):
            if 0 < torrent.num_complete < automation.get("rare_seed_threshold", 5):
                protected = True

        if protected:
            # Never stop a protected torrent. Resume it if a rule paused it.
            if torrent.state == TorrentState.PAUSED and rule_paused:
                await client.resume_torrent(torrent.hash)
                await client.remove_tags(torrent.hash, [AUTOPAUSE_TAG])
                actions["resumed"] += 1
            return

        # Seed-then-cleanup once goals and tracker minimums are met (opt-in only).
        cleanup_enabled = seed_then_cleanup or automation.get("seed_then_cleanup_enabled", False)
        if cleanup_enabled and hr_met and goal_met(torrent):
            await client.delete_torrent(torrent.hash, delete_files=True)
            await conn.execute(
                "UPDATE download_history SET status = 'removed', updated_at = NOW() WHERE torrent_hash = $1",
                torrent.hash,
            )
            await conn.execute("DELETE FROM torrent_rule_state WHERE torrent_hash = $1", torrent.hash)
            actions["cleaned"] += 1
            return

        # Determine whether any rule wants this torrent paused now.
        wants_pause = False

        if automation.get("offpeak_action") == "pause" and self._offpeak_restrict(automation, hour, weekday):
            wants_pause = True

        if automation.get("active_peer_pause_enabled"):
            if torrent.num_incomplete == 0:
                since = state.get("no_peers_since")
                if since is None:
                    await self._set_timer(conn, torrent.hash, "no_peers_since", now_dt)
                    since = now_dt
                elapsed_min = (now_dt - since).total_seconds() / 60.0
                if elapsed_min >= automation.get("active_peer_pause_minutes", 30):
                    wants_pause = True
            elif state.get("no_peers_since") is not None:
                await self._set_timer(conn, torrent.hash, "no_peers_since", None)

        if wants_pause and torrent.state == TorrentState.SEEDING:
            await client.pause_torrent(torrent.hash)
            await client.set_tags(torrent.hash, [AUTOPAUSE_TAG])
            actions["paused"] += 1
        elif not wants_pause and rule_paused and torrent.state == TorrentState.PAUSED:
            await client.resume_torrent(torrent.hash)
            await client.remove_tags(torrent.hash, [AUTOPAUSE_TAG])
            actions["resumed"] += 1

    async def _handle_stall(self, conn, client, torrent, ctx, automation, state, now_dt) -> bool:
        """
        Track a stalled/errored download and, once the timeout passes, blocklist the
        release and reset the media item to 'wanted' so the wanted-search re-grabs it.
        Auto-recovery is opt-in (per-profile or global setting). Returns True on recovery.
        """
        # Only genuinely stuck downloads count as stalled. A torrent paused by the
        # disk-low or VPN kill-switch rules, or one waiting in the queue, also has
        # zero speed but must never be treated as stalled and auto-removed.
        stalled = torrent.state == TorrentState.ERROR or (
            torrent.state == TorrentState.DOWNLOADING and torrent.num_complete == 0 and torrent.download_speed == 0
        )

        if not stalled:
            if state.get("stalled_since") is not None:
                await self._set_timer(conn, torrent.hash, "stalled_since", None)
            return False

        since = state.get("stalled_since")
        if since is None:
            await self._set_timer(conn, torrent.hash, "stalled_since", now_dt)
            return False

        elapsed_min = (now_dt - since).total_seconds() / 60.0
        if elapsed_min < automation.get("stall_timeout_minutes", 60):
            return False

        media_type = (ctx or {}).get("media_type")
        media_id = (ctx or {}).get("media_id")
        title = (ctx or {}).get("torrent_title") or torrent.name

        # Blocklist the failing release so the re-search skips it.
        if media_type in _MEDIA_TABLES and media_id:
            try:
                await conn.execute(
                    """
                    INSERT INTO blocklist (media_type, media_id, release_title, reason)
                    SELECT $1, $2, $3, $4
                    WHERE NOT EXISTS (
                        SELECT 1 FROM blocklist
                        WHERE media_type = $1 AND media_id = $2 AND release_title = $3
                    )
                    """,
                    media_type,
                    media_id,
                    title,
                    "Auto-recovery: download stalled",
                )
            except Exception as e:
                logger.debug(f"Blocklist insert failed: {e}")

            # Reset the media item so the wanted-search picks it up again.
            table = _MEDIA_TABLES[media_type]
            await conn.execute(
                f"UPDATE {table} SET status = 'wanted', updated_at = NOW() WHERE id = $1",
                media_id,
            )

        await client.delete_torrent(torrent.hash, delete_files=True)
        await conn.execute(
            """
            UPDATE download_history
            SET status = 'failed', error_message = 'Auto-recovery: download stalled', updated_at = NOW()
            WHERE torrent_hash = $1
            """,
            torrent.hash,
        )
        await conn.execute("DELETE FROM torrent_rule_state WHERE torrent_hash = $1", torrent.hash)
        await create_notification(
            type="auto_recovery",
            title="Download auto-recovered",
            message=f"'{title}' stalled and was blocklisted and re-queued for a new release.",
            severity=SEVERITY_WARNING,
            data={"media_type": media_type, "media_id": media_id},
        )
        logger.info(f"Auto-recovered stalled download {torrent.hash[:8]} ({title})")
        return True


seeding_rules_engine = SeedingRulesEngine()


async def run_seeding_rules() -> Dict[str, Any]:
    return await seeding_rules_engine.run()
