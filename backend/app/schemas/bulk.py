from typing import Optional, List
from pydantic import BaseModel, Field


class BulkMonitorRequest(BaseModel):
    """Schema for bulk monitor/unmonitor operation"""

    ids: List[int] = Field(..., min_length=1)
    monitored: bool


class BulkDeleteRequest(BaseModel):
    """Schema for bulk delete operation"""

    ids: List[int] = Field(..., min_length=1)
    delete_files: bool = False


class BulkRenameRequest(BaseModel):
    """Schema for bulk rename operation"""

    ids: List[int] = Field(..., min_length=1)


class BulkRefreshMetadataRequest(BaseModel):
    """Schema for bulk metadata refresh operation"""

    ids: List[int] = Field(..., min_length=1)


class BulkRescanRequest(BaseModel):
    """Schema for bulk rescan operation"""

    ids: List[int] = Field(..., min_length=1)


class BulkTagsRequest(BaseModel):
    """Schema for bulk tags operation"""

    ids: List[int] = Field(..., min_length=1)
    add_tags: List[int] = Field(default_factory=list)
    remove_tags: List[int] = Field(default_factory=list)


class BulkMediaProfileRequest(BaseModel):
    """Schema for bulk media profile change"""

    ids: List[int] = Field(..., min_length=1)
    media_profile_id: int


class BulkRenameAllRequest(BaseModel):
    """Schema for renaming all files in library"""

    media_type: Optional[str] = None


class BulkOperationResult(BaseModel):
    """Schema for bulk operation result"""

    success: bool
    processed: int
    failed: int
    total: int
    errors: List[str] = Field(default_factory=list)
