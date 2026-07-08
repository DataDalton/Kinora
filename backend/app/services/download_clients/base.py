from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class TorrentState(str, Enum):
    """Torrent state enumeration"""

    DOWNLOADING = "downloading"
    SEEDING = "seeding"
    PAUSED = "paused"
    CHECKING = "checking"
    ERROR = "error"
    QUEUED = "queued"
    COMPLETED = "completed"


@dataclass
class TorrentInfo:
    """Standardized torrent information"""

    hash: str
    name: str
    state: TorrentState
    progress: float  # 0.0 to 1.0
    download_speed: int  # bytes/s
    upload_speed: int  # bytes/s
    downloaded: int  # bytes
    uploaded: int  # bytes
    size: int  # bytes
    seeders: int  # connected seeds
    leechers: int  # connected peers
    ratio: float
    eta: Optional[int] = None  # seconds
    save_path: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    added_on: Optional[int] = None  # timestamp
    completion_on: Optional[int] = None  # timestamp
    # Seeding / share-limit state
    ratio_limit: float = -1.0  # -1 use global, -2 unlimited
    seeding_time: int = 0  # seconds spent seeding
    seeding_time_limit: int = -1  # minutes, -1 global, -2 unlimited
    inactive_seeding_time_limit: int = -1  # minutes, -1 global, -2 unlimited
    force_start: bool = False
    super_seeding: bool = False
    sequential_download: bool = False
    # Swarm health
    availability: float = 0.0  # distributed copies available
    num_complete: int = 0  # seeds in the swarm
    num_incomplete: int = 0  # leechers in the swarm
    # Per-torrent speed limits (bytes/s, 0 = unlimited)
    dl_limit: int = 0
    up_limit: int = 0
    last_activity: Optional[int] = None  # timestamp of last upload/download
    tracker: Optional[str] = None  # currently working tracker URL


class BaseDownloadClient(ABC):
    """
    Base class for all download client implementations
    """

    name: str = ""
    client_type: str = ""

    @abstractmethod
    async def test_connection(self) -> bool:
        """Test if client is reachable and authenticated"""
        pass

    @abstractmethod
    async def add_torrent(
        self,
        torrent: str,  # magnet link or torrent file URL
        save_path: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        paused: bool = False,
    ) -> str:
        """
        Add a torrent to the client
        Returns torrent hash
        """
        pass

    @abstractmethod
    async def get_torrents(
        self,
        hashes: Optional[List[str]] = None,
        category: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> List[TorrentInfo]:
        """Get list of torrents, optionally filtered"""
        pass

    @abstractmethod
    async def get_torrent(self, hash: str) -> Optional[TorrentInfo]:
        """Get specific torrent by hash"""
        pass

    @abstractmethod
    async def pause_torrent(self, hash: str) -> bool:
        """Pause a torrent"""
        pass

    @abstractmethod
    async def resume_torrent(self, hash: str) -> bool:
        """Resume a torrent"""
        pass

    @abstractmethod
    async def delete_torrent(self, hash: str, delete_files: bool = False) -> bool:
        """Delete a torrent, optionally with files"""
        pass

    @abstractmethod
    async def set_category(self, hash: str, category: str) -> bool:
        """Set torrent category"""
        pass

    @abstractmethod
    async def set_tags(self, hash: str, tags: List[str]) -> bool:
        """Set torrent tags"""
        pass

    @abstractmethod
    async def get_torrent_files(self, hash: str) -> List[Dict[str, Any]]:
        """Get list of files in torrent"""
        pass

    @abstractmethod
    async def set_share_limits(
        self,
        hash: str,
        ratio_limit: float,
        seeding_time_limit: int,
        inactive_seeding_time_limit: int = -1,
    ) -> bool:
        """Set per-torrent ratio and seeding-time limits.

        Sentinels: -1 = use global limit, -2 = no limit. Times are in minutes.
        """
        pass

    @abstractmethod
    async def recheck_torrent(self, hash: str) -> bool:
        """Force a data recheck of the torrent"""
        pass

    @abstractmethod
    async def reannounce_torrent(self, hash: str) -> bool:
        """Force a reannounce to trackers"""
        pass

    @abstractmethod
    async def set_force_start(self, hash: str, enabled: bool) -> bool:
        """Enable or disable force-start (bypass queue limits)"""
        pass

    @abstractmethod
    async def set_super_seeding(self, hash: str, enabled: bool) -> bool:
        """Enable or disable super-seeding mode"""
        pass

    @abstractmethod
    async def set_sequential_download(self, hash: str, enabled: bool) -> bool:
        """Enable or disable sequential download"""
        pass

    @abstractmethod
    async def set_queue_priority(self, hash: str, action: str) -> bool:
        """Change queue priority. action: 'top' | 'bottom' | 'up' | 'down'."""
        pass

    @abstractmethod
    async def set_torrent_speed_limits(self, hash: str, download_limit: int, upload_limit: int) -> bool:
        """Set per-torrent download/upload speed limits in bytes/s (0 = unlimited)"""
        pass

    @abstractmethod
    async def set_global_speed_limits(self, download_limit: int, upload_limit: int) -> bool:
        """Set global download/upload speed limits in bytes/s (0 = unlimited)"""
        pass

    @abstractmethod
    async def toggle_alternative_speed_limits(self) -> bool:
        """Toggle the alternative (scheduled) speed-limit mode"""
        pass

    @abstractmethod
    async def get_transfer_info(self) -> Dict[str, Any]:
        """Get global transfer info (speeds, totals, alt-speed state)"""
        pass
