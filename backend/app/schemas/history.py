from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class DownloadHistoryBase(BaseModel):
    """Base download history schema"""

    media_type: str = Field(..., max_length=50)
    media_id: int
    episode_id: Optional[int] = None
    torrent_hash: str = Field(..., max_length=100)
    torrent_title: str
    indexer: str = Field(..., max_length=100)
    indexer_page_url: Optional[str] = None
    torrent_url: Optional[str] = None
    magnet_link: Optional[str] = None
    info_hash: Optional[str] = Field(None, max_length=64)
    quality: Optional[str] = Field(None, max_length=50)
    source: Optional[str] = Field(None, max_length=50)
    size: Optional[int] = None
    seeders: Optional[int] = None
    download_client: Optional[str] = Field(None, max_length=50)
    save_path: Optional[str] = None


class DownloadHistoryCreate(DownloadHistoryBase):
    """Schema for creating download history entry"""

    pass


class DownloadHistoryUpdate(BaseModel):
    """Schema for updating download history"""

    status: Optional[str] = Field(None, max_length=50)
    progress: Optional[float] = None
    error_message: Optional[str] = None
    completed_at: Optional[datetime] = None
    was_upgrade: Optional[bool] = None


class DownloadHistory(DownloadHistoryBase):
    """Schema for download history response"""

    id: int
    status: str
    progress: float
    grab_mode: Optional[str] = None
    error_message: Optional[str] = None
    was_upgrade: bool
    started_at: datetime
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DownloadHistoryStats(BaseModel):
    """Schema for download history statistics"""

    total_downloads: int
    completed: int
    failed: int
    in_progress: int
    total_size_bytes: int
    upgrades: int


class DownloadHistoryFilter(BaseModel):
    """Schema for filtering download history"""

    media_type: Optional[str] = None
    media_id: Optional[int] = None
    status: Optional[str] = None
    indexer: Optional[str] = None
    was_upgrade: Optional[bool] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
