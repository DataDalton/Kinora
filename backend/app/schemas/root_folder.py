from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator


class RootFolderBase(BaseModel):
    """Base root folder schema"""

    media_type: Literal["movies", "shows", "anime", "music"]
    name: str = Field(..., max_length=100)
    root_path: str = Field(..., max_length=500)
    download_path: Optional[str] = Field(None, max_length=500)
    priority: int = 0
    fill_threshold_percent: Optional[int] = Field(None, ge=0, le=100)
    fill_threshold_gb: Optional[int] = Field(None, ge=0)
    is_active: bool = True


class RootFolderCreate(RootFolderBase):
    """Schema for creating a root folder"""

    pass


class RootFolderUpdate(BaseModel):
    """Schema for updating a root folder"""

    name: Optional[str] = Field(None, max_length=100)
    root_path: Optional[str] = Field(None, max_length=500)
    download_path: Optional[str] = Field(None, max_length=500)
    priority: Optional[int] = None
    fill_threshold_percent: Optional[int] = Field(None, ge=0, le=100)
    fill_threshold_gb: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class RootFolderResponse(RootFolderBase):
    """Schema for root folder response"""

    id: int
    total_space_bytes: Optional[int] = None
    free_space_bytes: Optional[int] = None
    last_health_check: Optional[datetime] = None
    health_status: str = "unknown"
    health_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RootFolderWithStats(RootFolderResponse):
    """Root folder response with computed stats included as fields"""

    used_space_bytes: Optional[int] = None
    used_percent: Optional[float] = None


class FolderSelectionSettingsBase(BaseModel):
    """Base folder selection settings schema"""

    media_type: Literal["movies", "shows", "anime", "music"]
    selection_mode: Literal["most_free_space", "priority", "fill_threshold"] = "most_free_space"


class FolderSelectionSettingsCreate(FolderSelectionSettingsBase):
    """Schema for creating folder selection settings"""

    pass


class FolderSelectionSettingsUpdate(BaseModel):
    """Schema for updating folder selection settings"""

    selection_mode: Literal["most_free_space", "priority", "fill_threshold"]


class FolderSelectionSettingsResponse(FolderSelectionSettingsBase):
    """Schema for folder selection settings response"""

    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FolderTestRequest(BaseModel):
    """Schema for testing a folder path"""

    root_path: str
    download_path: Optional[str] = None


class FolderTestResponse(BaseModel):
    """Schema for folder test result"""

    success: bool
    root_path_accessible: bool
    root_path_writable: bool
    download_path_accessible: bool
    download_path_writable: bool
    same_filesystem: bool
    hardlink_supported: bool
    message: Optional[str] = None


class DriveStats(BaseModel):
    """Schema for drive-level statistics"""

    drive: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    used_percent: float
    folder_count: int
    folders: list[RootFolderWithStats] = []


class FolderHealthSummary(BaseModel):
    """Schema for folder health summary"""

    total_folders: int
    healthy_count: int
    warning_count: int
    error_count: int
    unknown_count: int


class BrowseDirectoryRequest(BaseModel):
    """Schema for directory browse request"""

    path: Optional[str] = None


class BrowseDirectoryResponse(BaseModel):
    """Schema for directory browse response"""

    path: str
    parent: Optional[str] = None
    directories: list[str] = []
    is_root: bool = False
