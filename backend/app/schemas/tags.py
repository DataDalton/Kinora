from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class TagBase(BaseModel):
    """Base tag schema"""

    name: str = Field(..., min_length=1, max_length=100)
    color: Optional[str] = Field("#6366f1", max_length=20)


class TagCreate(TagBase):
    """Schema for creating a tag"""

    pass


class TagUpdate(BaseModel):
    """Schema for updating a tag"""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    color: Optional[str] = Field(None, max_length=20)


class Tag(TagBase):
    """Schema for tag response"""

    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class MediaTagCreate(BaseModel):
    """Schema for tagging media items"""

    tag_ids: List[int] = Field(..., min_length=1)


class MediaTagResponse(BaseModel):
    """Schema for media tag response"""

    id: int
    tag_id: int
    media_type: str
    media_id: int
    created_at: datetime
    tag: Optional[Tag] = None

    model_config = {"from_attributes": True}


class BulkTagUpdate(BaseModel):
    """Schema for bulk adding/removing tags from multiple items"""

    media_ids: List[int] = Field(..., min_length=1)
    add_tags: List[int] = Field(default_factory=list)
    remove_tags: List[int] = Field(default_factory=list)
