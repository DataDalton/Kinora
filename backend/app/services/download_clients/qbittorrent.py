from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio
import json
import re

from app.services.download_clients.base import (
    BaseDownloadClient,
    TorrentInfo,
    TorrentState,
)
from app.core.config import settings
from app.core.http_client import http_get, http_post


class QBittorrentClient(BaseDownloadClient):
    """
    qBittorrent download client implementation
    Uses qBittorrent Web API
    """

    name = "qBittorrent"
    client_type = "qbittorrent"

    def __init__(
        self,
        host: str = None,
        port: int = None,
        username: str = None,
        password: str = None,
        use_ssl: bool = False,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_ssl = use_ssl

        self.base_url = None
        if self.host and self.port:
            protocol = "https" if self.use_ssl else "http"
            self.base_url = f"{protocol}://{self.host}:{self.port}/api/v2"

        self._cookie: Optional[str] = None

    async def _login(self) -> bool:
        """Authenticate with qBittorrent"""
        response = await http_post(
            f"{self.base_url}/auth/login",
            data={"username": self.username, "password": self.password},
        )

        if response.text == "Ok.":
            self._cookie = response.cookies.get("SID")
            return True

        return False

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        _reauth: bool = True,
    ) -> Any:
        """Make authenticated request to qBittorrent API"""
        if not self._cookie:
            await self._login()

        cookies = {"SID": self._cookie} if self._cookie else None

        if method == "GET":
            response = await http_get(f"{self.base_url}/{endpoint}", params=data, cookies=cookies)
        else:
            response = await http_post(
                f"{self.base_url}/{endpoint}",
                data=data,
                files=files,
                cookies=cookies,
            )

        # A 403 means the session expired. Re-login and retry exactly once so a
        # persistently rejecting client (bad credentials) surfaces as an error
        # instead of recursing until RecursionError.
        if response.status_code == 403 and _reauth:
            self._cookie = None
            await self._login()
            return await self._request(method, endpoint, data, files, _reauth=False)

        response.raise_for_status()

        if response.text:
            try:
                return response.json()
            except Exception:
                return response.text

        return None

    async def test_connection(self) -> bool:
        """Test if qBittorrent is reachable"""
        try:
            version = await self._request("GET", "app/version")
            return version is not None
        except Exception:
            return False

    @staticmethod
    def _magnet_hash(torrent: str) -> Optional[str]:
        """Extract the v1 info hash (40-char hex) from a magnet URI, if present."""
        match = re.search(r"xt=urn:btih:([0-9a-fA-F]{40})", torrent)
        return match.group(1).lower() if match else None

    async def add_torrent(
        self,
        torrent: str,
        save_path: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        paused: bool = False,
        known_hash: Optional[str] = None,
    ) -> str:
        """
        Add a torrent (magnet or .torrent URL) and return its info hash.

        qBittorrent's add endpoint does not return the hash, so it is resolved in
        this order: a caller-supplied known_hash, the hash embedded in a magnet URI,
        then the hash that newly appears in the torrent list after adding.
        """
        # Snapshot existing hashes before adding so the new one can be identified
        # even for .torrent URLs that carry no hash in the input string.
        existing = {t.hash.lower() for t in await self.get_torrents()}

        data = {"urls": torrent}
        if save_path:
            data["savepath"] = save_path
        if category:
            data["category"] = category
        if tags:
            data["tags"] = ",".join(tags)
        if paused:
            # qBittorrent 5.x renamed this parameter; send both so the torrent is
            # added stopped on every version for the validate-before-resume flow.
            data["paused"] = "true"
            data["stopped"] = "true"

        await self._request("POST", "torrents/add", data=data)

        target = (known_hash or self._magnet_hash(torrent) or "").lower() or None
        return await self._resolve_added_hash(target, existing)

    async def _resolve_added_hash(
        self,
        target: Optional[str],
        existing: set,
        max_attempts: int = 20,
        delay: float = 0.5,
    ) -> str:
        """
        Poll the torrent list until the added torrent is identifiable, by either the
        target hash appearing or a single new hash showing up versus the pre-add set.
        """
        for _ in range(max_attempts):
            torrents = await self.get_torrents()
            by_hash = {t.hash.lower(): t.hash for t in torrents}
            if target and target in by_hash:
                return by_hash[target]
            new_hashes = [orig for lower, orig in by_hash.items() if lower not in existing]
            if len(new_hashes) == 1:
                return new_hashes[0]
            if new_hashes and target is None:
                # Multiple new torrents and no target to disambiguate: take the first.
                return new_hashes[0]
            await asyncio.sleep(delay)

        if target:
            # The add succeeded and the hash is known even if the list has not caught up.
            return target
        raise Exception("Torrent was added but did not appear in qBittorrent in time")

    async def get_torrents(
        self,
        hashes: Optional[List[str]] = None,
        category: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> List[TorrentInfo]:
        """Get list of torrents"""
        params = {}
        if hashes:
            params["hashes"] = "|".join(hashes)
        if category:
            params["category"] = category
        if tag:
            params["tag"] = tag

        data = await self._request("GET", "torrents/info", data=params)

        if not data:
            return []

        return [self._parse_torrent(t) for t in data]

    async def get_torrent(self, hash: str) -> Optional[TorrentInfo]:
        """Get specific torrent"""
        torrents = await self.get_torrents(hashes=[hash])
        return torrents[0] if torrents else None

    async def _request_with_fallback(self, primary: str, fallback: str, hash: str) -> None:
        """
        Call a torrents endpoint, falling back to a legacy name on 404. qBittorrent 5.x
        renamed pause/resume to stop/start; this keeps both API versions working.
        """
        try:
            await self._request("POST", primary, data={"hashes": hash})
        except Exception as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            if status_code == 404:
                await self._request("POST", fallback, data={"hashes": hash})
            else:
                raise

    async def pause_torrent(self, hash: str) -> bool:
        """Pause (stop) a torrent. Uses the v5 endpoint with a v4 fallback."""
        await self._request_with_fallback("torrents/stop", "torrents/pause", hash)
        return True

    async def resume_torrent(self, hash: str) -> bool:
        """Resume (start) a torrent. Uses the v5 endpoint with a v4 fallback."""
        await self._request_with_fallback("torrents/start", "torrents/resume", hash)
        return True

    async def delete_torrent(self, hash: str, delete_files: bool = False) -> bool:
        """Delete a torrent"""
        await self._request(
            "POST",
            "torrents/delete",
            data={"hashes": hash, "deleteFiles": str(delete_files).lower()},
        )
        return True

    async def set_category(self, hash: str, category: str) -> bool:
        """Set torrent category"""
        await self._request("POST", "torrents/setCategory", data={"hashes": hash, "category": category})
        return True

    async def set_tags(self, hash: str, tags: List[str]) -> bool:
        """Set torrent tags"""
        await self._request("POST", "torrents/addTags", data={"hashes": hash, "tags": ",".join(tags)})
        return True

    async def remove_tags(self, hash: str, tags: List[str]) -> bool:
        """Remove specific tags from a torrent"""
        await self._request("POST", "torrents/removeTags", data={"hashes": hash, "tags": ",".join(tags)})
        return True

    async def add_category(self, name: str, save_path: str) -> bool:
        """Add or update a category"""
        await self._request("POST", "torrents/createCategory", data={"category": name, "savePath": save_path})
        return True

    async def get_torrent_files(self, hash: str) -> List[Dict[str, Any]]:
        """Get list of files in torrent"""
        files = await self._request("GET", "torrents/files", data={"hash": hash})
        return files or []

    async def set_share_limits(
        self,
        hash: str,
        ratio_limit: float,
        seeding_time_limit: int,
        inactive_seeding_time_limit: int = -1,
    ) -> bool:
        """Set per-torrent ratio and seeding-time limits (minutes; -1 global, -2 none)."""
        await self._request(
            "POST",
            "torrents/setShareLimits",
            data={
                "hashes": hash,
                "ratioLimit": ratio_limit,
                "seedingTimeLimit": seeding_time_limit,
                "inactiveSeedingTimeLimit": inactive_seeding_time_limit,
            },
        )
        return True

    async def recheck_torrent(self, hash: str) -> bool:
        """Force a data recheck of the torrent"""
        await self._request("POST", "torrents/recheck", data={"hashes": hash})
        return True

    async def reannounce_torrent(self, hash: str) -> bool:
        """Force a reannounce to trackers"""
        await self._request("POST", "torrents/reannounce", data={"hashes": hash})
        return True

    async def set_force_start(self, hash: str, enabled: bool) -> bool:
        """Enable or disable force-start (bypass queue limits)"""
        await self._request(
            "POST",
            "torrents/setForceStart",
            data={"hashes": hash, "value": "true" if enabled else "false"},
        )
        return True

    async def set_super_seeding(self, hash: str, enabled: bool) -> bool:
        """Enable or disable super-seeding mode"""
        await self._request(
            "POST",
            "torrents/setSuperSeeding",
            data={"hashes": hash, "value": "true" if enabled else "false"},
        )
        return True

    async def set_sequential_download(self, hash: str, enabled: bool) -> bool:
        """Enable or disable sequential download.

        qBittorrent only exposes a toggle, so read the current state and toggle
        only when it differs from the requested value.
        """
        torrent = await self.get_torrent(hash)
        if torrent is not None and torrent.sequential_download == enabled:
            return True
        await self._request("POST", "torrents/toggleSequentialDownload", data={"hashes": hash})
        return True

    async def set_queue_priority(self, hash: str, action: str) -> bool:
        """Change queue priority. action: 'top' | 'bottom' | 'up' | 'down'."""
        endpoint_map = {
            "top": "torrents/topPrio",
            "bottom": "torrents/bottomPrio",
            "up": "torrents/increasePrio",
            "down": "torrents/decreasePrio",
        }
        endpoint = endpoint_map.get(action)
        if not endpoint:
            raise ValueError(f"Invalid queue action: {action}")
        await self._request("POST", endpoint, data={"hashes": hash})
        return True

    async def set_torrent_speed_limits(self, hash: str, download_limit: int, upload_limit: int) -> bool:
        """Set per-torrent download/upload limits in bytes/s (0 = unlimited)."""
        await self._request(
            "POST",
            "torrents/setDownloadLimit",
            data={"hashes": hash, "limit": download_limit},
        )
        await self._request(
            "POST",
            "torrents/setUploadLimit",
            data={"hashes": hash, "limit": upload_limit},
        )
        return True

    async def set_global_speed_limits(self, download_limit: int, upload_limit: int) -> bool:
        """Set global download/upload limits in bytes/s (0 = unlimited)."""
        await self._request("POST", "transfer/setDownloadLimit", data={"limit": download_limit})
        await self._request("POST", "transfer/setUploadLimit", data={"limit": upload_limit})
        return True

    async def toggle_alternative_speed_limits(self) -> bool:
        """Toggle the alternative (scheduled) speed-limit mode"""
        await self._request("POST", "transfer/toggleSpeedLimitsMode")
        return True

    async def get_transfer_info(self) -> Dict[str, Any]:
        """Get global transfer info (speeds, totals, alt-speed state)."""
        data = await self._request("GET", "transfer/info")
        return data or {}

    async def get_preferences(self) -> Dict[str, Any]:
        """Get qBittorrent application preferences."""
        data = await self._request("GET", "app/preferences")
        return data or {}

    async def set_preferences(self, prefs: Dict[str, Any]) -> bool:
        """Set qBittorrent application preferences."""
        await self._request("POST", "app/setPreferences", data={"json": json.dumps(prefs)})
        return True

    async def get_torrent_trackers(self, hash: str) -> List[Dict[str, Any]]:
        """Get tracker list and status for a torrent."""
        data = await self._request("GET", "torrents/trackers", data={"hash": hash})
        return data or []

    async def get_piece_states(self, hash: str) -> List[int]:
        """Get piece states (0 = not downloaded, 1 = downloading, 2 = downloaded)."""
        data = await self._request("GET", "torrents/pieceStates", data={"hash": hash})
        return data or []

    async def get_network_interfaces(self) -> List[Dict[str, str]]:
        """List network interfaces qBittorrent can bind to."""
        data = await self._request("GET", "app/networkInterfaceList")
        return data or []

    async def get_network_interface_addresses(self, interface: str) -> List[str]:
        """List addresses for a given network interface."""
        data = await self._request("GET", "app/networkInterfaceAddressList", data={"iface": interface})
        return data or []

    def _parse_torrent(self, data: Dict[str, Any]) -> TorrentInfo:
        """Parse qBittorrent torrent data into TorrentInfo"""
        state_map = {
            "downloading": TorrentState.DOWNLOADING,
            "stalledDL": TorrentState.DOWNLOADING,
            "uploading": TorrentState.SEEDING,
            "stalledUP": TorrentState.SEEDING,
            "pausedDL": TorrentState.PAUSED,
            "pausedUP": TorrentState.PAUSED,
            "checkingDL": TorrentState.CHECKING,
            "checkingUP": TorrentState.CHECKING,
            "queuedDL": TorrentState.QUEUED,
            "queuedUP": TorrentState.QUEUED,
            "error": TorrentState.ERROR,
            "missingFiles": TorrentState.ERROR,
        }

        state = state_map.get(data.get("state", ""), TorrentState.DOWNLOADING)

        tags = data.get("tags", "").split(",") if data.get("tags") else []
        tags = [t.strip() for t in tags if t.strip()]

        raw_state = data.get("state", "")

        return TorrentInfo(
            hash=data.get("hash", ""),
            name=data.get("name", ""),
            state=state,
            progress=data.get("progress", 0.0),
            download_speed=data.get("dlspeed", 0),
            upload_speed=data.get("upspeed", 0),
            downloaded=data.get("downloaded", 0),
            uploaded=data.get("uploaded", 0),
            size=data.get("size", 0),
            seeders=data.get("num_seeds", 0),
            leechers=data.get("num_leechs", 0),
            ratio=data.get("ratio", 0.0),
            eta=data.get("eta") if data.get("eta") != 8640000 else None,
            save_path=data.get("save_path"),
            category=data.get("category"),
            tags=tags,
            added_on=data.get("added_on"),
            completion_on=data.get("completion_on"),
            ratio_limit=data.get("ratio_limit", -1.0),
            seeding_time=data.get("seeding_time", 0),
            seeding_time_limit=data.get("seeding_time_limit", -1),
            inactive_seeding_time_limit=data.get("inactive_seeding_time_limit", -1),
            force_start=data.get("force_start", False),
            super_seeding=data.get("super_seeding", False),
            sequential_download=data.get("seq_dl", False),
            availability=data.get("availability", 0.0),
            num_complete=data.get("num_complete", 0),
            num_incomplete=data.get("num_incomplete", 0),
            dl_limit=data.get("dl_limit", 0),
            up_limit=data.get("up_limit", 0),
            last_activity=data.get("last_activity"),
            tracker=data.get("tracker") or None,
        )


# Global client instance - lazily initialized from database config
qbittorrent_client = None


async def get_qbittorrent_client():
    """
    Factory function to get qBittorrent client instance from database config.
    Returns None if setup is not complete.
    """
    global qbittorrent_client

    if qbittorrent_client is not None:
        return qbittorrent_client

    try:
        from app.db import get_pool
        from app.api.v1.endpoints.setup import decrypt_value

        pool = await get_pool()
        async with pool.acquire() as conn:
            # Check if qBittorrent is configured
            client_row = await conn.fetchrow(
                "SELECT * FROM download_clients WHERE client_type = 'qbittorrent' AND is_enabled = TRUE LIMIT 1"
            )

            if not client_row:
                return None

            # Decrypt password
            password = decrypt_value(client_row["encrypted_password"])

            # Create client instance
            qbittorrent_client = QBittorrentClient(
                host=client_row["host"],
                port=client_row["port"],
                username=client_row["username"],
                password=password,
                use_ssl=client_row["use_ssl"],
            )

            return qbittorrent_client

    except Exception as e:
        # Setup not complete or database not ready
        return None
