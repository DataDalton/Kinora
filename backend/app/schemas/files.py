from typing import Optional, List
from pydantic import BaseModel, Field


class FileInfo(BaseModel):
    """Schema for a single media file with detected quality attributes."""

    file_path: str
    file_name: str
    file_size: Optional[int] = None
    quality: Optional[str] = None
    resolution: Optional[str] = None
    codec: Optional[str] = None
    audio_codec: Optional[str] = None
    audio_channels: Optional[str] = None
    container: Optional[str] = None
    bit_depth: Optional[str] = None
    hdr: bool = False
    created_at: Optional[str] = None


class QualityCutoff(BaseModel):
    """Cutoff status for a media item, shown on the detail page file panel."""

    meets_cutoff: bool
    current_quality: Optional[str] = None
    cutoff_quality: str
    upgrade_allowed: bool


class MediaFiles(BaseModel):
    """Schema for media item files"""

    media_type: str
    media_id: int
    media_title: str
    root_folder: Optional[str] = None
    files: List[FileInfo] = Field(default_factory=list)
    total_size: int = 0
    grab_mode: Optional[str] = None
    quality_cutoff: Optional[QualityCutoff] = None


class RenameFileRequest(BaseModel):
    """Schema for renaming a file"""

    file_path: str
    new_name: str = Field(..., min_length=1, max_length=500)


class ManualImportRequest(BaseModel):
    """Schema for manual file import"""

    file_path: str
    episode_id: Optional[int] = None


class DeleteFilesRequest(BaseModel):
    """Schema for deleting media files"""

    delete_files: bool = False


class FileOperationResult(BaseModel):
    """Schema for file operation result"""

    success: bool
    message: str
    old_path: Optional[str] = None
    new_path: Optional[str] = None
