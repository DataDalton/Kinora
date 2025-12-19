from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class BlocklistBase(BaseModel):
    """Base blocklist schema"""

    media_type: str = Field(..., max_length=50)
    media_id: int
    release_title: str = Field(..., max_length=1000)
    reason: Optional[str] = Field(None, max_length=500)


class BlocklistCreate(BlocklistBase):
    """Schema for creating a blocklist entry"""

    pass


class BlocklistEntry(BlocklistBase):
    """Schema for blocklist entry response"""

    id: int
    blocked_at: datetime

    model_config = {"from_attributes": True}


class BulkBlocklistCreate(BaseModel):
    """Schema for bulk adding to blocklist"""

    entries: List[BlocklistCreate] = Field(..., min_length=1)


class BlocklistCheck(BaseModel):
    """Schema for checking if a release is blocklisted"""

    media_type: str = Field(..., max_length=50)
    media_id: int
    release_title: str = Field(..., max_length=1000)


class BlocklistCheckResult(BaseModel):
    """Schema for blocklist check result"""

    is_blocked: bool
    entry: Optional[BlocklistEntry] = None
