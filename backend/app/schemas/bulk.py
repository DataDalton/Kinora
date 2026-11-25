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
    """Schema for previewing a rename of every library file, optionally scoped to one media profile"""

    media_type: Optional[str] = None
    media_types: Optional[List[str]] = None
    media_profile_id: Optional[int] = None


class RenamePreviewEntry(BaseModel):
    """One file in a rename preview or a rename apply result"""

    mediaType: str
    itemId: int
    itemTitle: Optional[str] = None
    oldPath: Optional[str] = None
    newPath: Optional[str] = None
    # Preview statuses are change, unchanged, conflict and error. An apply adds applied and stale.
    status: str
    message: Optional[str] = None


class RenamePreviewCounts(BaseModel):
    """Number of preview entries per status"""

    change: int = 0
    unchanged: int = 0
    conflict: int = 0
    error: int = 0


class RenamePreviewResponse(BaseModel):
    """Every file a rename would touch, computed without changing anything on disk"""

    entries: List[RenamePreviewEntry] = Field(default_factory=list)
    counts: RenamePreviewCounts
    total: int


class RenameApplyEntry(BaseModel):
    """A previewed change to apply, with the paths the preview showed"""

    mediaType: str
    itemId: int
    oldPath: str
    newPath: str


class RenameApplyRequest(BaseModel):
    """The change entries of a preview, sent back to apply exactly those moves"""

    entries: List[RenameApplyEntry] = Field(..., min_length=1)


class RenameApplyResult(BaseModel):
    """Outcome of applying a previewed rename, per file and in total"""

    success: bool
    processed: int
    failed: int
    total: int
    errors: List[str] = Field(default_factory=list)
    applied: int = 0
    stale: int = 0
    conflict: int = 0
    entries: List[RenamePreviewEntry] = Field(default_factory=list)


class BulkOperationResult(BaseModel):
    """Schema for bulk operation result"""

    success: bool
    processed: int
    failed: int
    total: int
    errors: List[str] = Field(default_factory=list)
