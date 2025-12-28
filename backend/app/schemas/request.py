from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Any, Dict
from datetime import datetime


class MediaRequestCreate(BaseModel):
    """Schema for creating a new media request"""

    mediaType: str = Field(validation_alias="media_type")
    externalId: int = Field(validation_alias="external_id")
    title: str
    posterPath: Optional[str] = Field(default=None, validation_alias="poster_path")
    year: Optional[int] = None
    overview: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    requestNotes: Optional[str] = Field(default=None, validation_alias="request_notes")
    mediaProfileId: Optional[int] = Field(default=None, validation_alias="media_profile_id")
    rootFolderId: Optional[int] = Field(default=None, validation_alias="root_folder_id")
    autoSearch: bool = Field(default=True, validation_alias="auto_search")

    model_config = ConfigDict(populate_by_name=True)


class MediaRequestResponse(BaseModel):
    """Schema for media request response with full details"""

    id: int
    userId: int = Field(validation_alias="user_id")
    username: str
    mediaType: str = Field(validation_alias="media_type")
    externalId: int = Field(validation_alias="external_id")
    title: str
    posterPath: Optional[str] = Field(default=None, validation_alias="poster_path")
    year: Optional[int] = None
    overview: Optional[str] = None
    status: str
    requestNotes: Optional[str] = Field(default=None, validation_alias="request_notes")
    requestedAt: datetime = Field(validation_alias="requested_at")
    reviewedAt: Optional[datetime] = Field(default=None, validation_alias="reviewed_at")
    reviewedBy: Optional[int] = Field(default=None, validation_alias="reviewed_by")
    reviewerUsername: Optional[str] = Field(default=None, validation_alias="reviewer_username")
    reviewNotes: Optional[str] = Field(default=None, validation_alias="review_notes")
    createdMediaId: Optional[int] = Field(default=None, validation_alias="created_media_id")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class MediaRequestReview(BaseModel):
    """Schema for reviewing a media request (approve or deny)"""

    notes: Optional[str] = None


class MediaRequestCount(BaseModel):
    """Schema for media request counts by status"""

    pending: int
    approved: int
    denied: int
    total: int
