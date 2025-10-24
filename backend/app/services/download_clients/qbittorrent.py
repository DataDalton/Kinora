import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.services.download_clients.base import (
    BaseDownloadClient,
    TorrentInfo,
    TorrentState,
)
from app.core.config import settings


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
        self.host = host or settings.QBITTORRENT_HOST
        self.port = port or settings.QBITTORRENT_PORT
        self.username = username or settings.QBITTORRENT_USERNAME
        self.password = password or settings.QBITTORRENT_PASSWORD
        self.use_ssl = use_ssl

        protocol = "https" if self.use_ssl else "http"
        self.base_url = f"{protocol}://{self.host}:{self.port}/api/v2"

        self._cookie: Optional[str] = None

    async def _login(self) -> bool:
        """Authenticate with qBittorrent"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
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
    ) -> Any:
        """Make authenticated request to qBittorrent API"""
        if not self._cookie:
            await self._login()

        cookies = {"SID": self._cookie} if self._cookie else None

        async with httpx.AsyncClient() as client:
            if method == "GET":
                response = await client.get(
                    f"{self.base_url}/{endpoint}", params=data, cookies=cookies
                )
            else:
                response = await client.post(
                    f"{self.base_url}/{endpoint}",
                    data=data,
                    files=files,
                    cookies=cookies,
                )

            if response.status_code == 403:
                await self._login()
                return await self._request(method, endpoint, data, files)

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

    async def add_torrent(
        self,
        torrent: str,
        save_path: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        paused: bool = False,
    ) -> str:
        """Add a torrent (magnet or URL)"""
        data = {"urls": torrent}

        if save_path:
            data["savepath"] = save_path
        if category:
            data["category"] = category
        if tags:
            data["tags"] = ",".join(tags)
        if paused:
            data["paused"] = "true"

        await self._request("POST", "torrents/add", data=data)

        # qBittorrent doesn't return hash directly, need to find it
        await self._wait_for_torrent(torrent)

        torrents = await self.get_torrents()
        for t in torrents:
            if torrent in t.name or (
                torrent.startswith("magnet:") and torrent in str(t.hash)
            ):
                return t.hash

        raise Exception("Failed to retrieve torrent hash after adding")

    async def _wait_for_torrent(self, torrent: str, max_attempts: int = 10):
        """Wait for torrent to appear in client"""
        import asyncio

        for _ in range(max_attempts):
            await asyncio.sleep(0.5)
            torrents = await self.get_torrents()
            for t in torrents:
                if torrent in t.name:
                    return
        return

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

    async def pause_torrent(self, hash: str) -> bool:
        """Pause a torrent"""
        await self._request("POST", "torrents/pause", data={"hashes": hash})
        return True

    async def resume_torrent(self, hash: str) -> bool:
        """Resume a torrent"""
        await self._request("POST", "torrents/resume", data={"hashes": hash})
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
        await self._request(
            "POST", "torrents/setCategory", data={"hashes": hash, "category": category}
        )
        return True

    async def set_tags(self, hash: str, tags: List[str]) -> bool:
        """Set torrent tags"""
        await self._request(
            "POST", "torrents/addTags", data={"hashes": hash, "tags": ",".join(tags)}
        )
        return True

    async def get_torrent_files(self, hash: str) -> List[Dict[str, Any]]:
        """Get list of files in torrent"""
        files = await self._request("GET", "torrents/files", data={"hash": hash})
        return files or []

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
        )


qbittorrent_client = QBittorrentClient()
