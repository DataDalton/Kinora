from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator
import json


def parseJsonField(value):
    """Parse a field that might be a JSON string or already a list/dict."""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
    return value


class MovieBase(BaseModel):
    """Base movie schema"""

    title: str = Field(..., max_length=255)
    original_title: Optional[str] = Field(None, max_length=255)
    overview: Optional[str] = None
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    release_date: Optional[datetime] = None
    genres: Optional[List[str]] = None
    rating: Optional[float] = None
    vote_count: Optional[int] = None
    popularity: Optional[float] = None
    tmdb_id: Optional[int] = None
    imdb_id: Optional[str] = None
    monitored: bool = True
    media_profile_id: Optional[int] = None
    root_folder_id: Optional[int] = None


class MovieCreate(MovieBase):
    """Schema for creating a movie"""

    pass


class MovieUpdate(BaseModel):
    """Schema for updating a movie"""

    title: Optional[str] = Field(None, max_length=255)
    monitored: Optional[bool] = None
    media_profile_id: Optional[int] = None
    root_folder_id: Optional[int] = None
    status: Optional[str] = None


class Movie(MovieBase):
    """Schema for movie response"""

    id: int
    status: str
    runtime: Optional[int] = None
    tagline: Optional[str] = None
    production_companies: Optional[List[Dict[str, Any]]] = None
    collection_id: Optional[int] = None
    collection_name: Optional[str] = None
    has_file: bool
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    quality_detected: Optional[str] = None
    codec: Optional[str] = None
    resolution: Optional[str] = None
    upgrade_allowed: Optional[bool] = None
    created_at: datetime
    updated_at: datetime

    @field_validator("genres", "production_companies", mode="before")
    @classmethod
    def parseJsonFields(cls, value):
        """Handle JSON string fields from database for backwards compatibility."""
        return parseJsonField(value)

    class Config:
        from_attributes = True


class MovieSearch(BaseModel):
    """Schema for movie search response from TMDB"""

    tmdb_id: int
    title: str
    original_title: Optional[str] = None
    overview: Optional[str] = None
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    release_date: Optional[str] = None
    genres: Optional[List[str]] = None
    rating: Optional[float] = None
    vote_count: Optional[int] = None
    popularity: Optional[float] = None
