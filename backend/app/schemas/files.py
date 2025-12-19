from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class FileInfo(BaseModel):
    """Schema for file information"""

    path: str
    name: str
    size: int
    extension: str
    is_directory: bool
    modified_at: datetime
    quality: Optional[str] = None
    codec: Optional[str] = None
    resolution: Optional[str] = None


class MediaFiles(BaseModel):
    """Schema for media item files"""

    media_type: str
    media_id: int
    media_title: str
    root_folder: Optional[str] = None
    files: List[FileInfo] = Field(default_factory=list)
    total_size: int = 0


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
