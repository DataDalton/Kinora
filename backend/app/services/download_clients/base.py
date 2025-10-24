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
    seeders: int
    leechers: int
    ratio: float
    eta: Optional[int] = None  # seconds
    save_path: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    added_on: Optional[int] = None  # timestamp
    completion_on: Optional[int] = None  # timestamp


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
