from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class MovieBase(BaseModel):
    """Base movie schema"""

    title: str = Field(..., max_length=255)
    original_title: Optional[str] = Field(None, max_length=255)
    overview: Optional[str] = None
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    release_date: Optional[datetime] = None
    genres: Optional[List[Dict[str, Any]]] = None
    rating: Optional[float] = None
    vote_count: Optional[int] = None
    popularity: Optional[float] = None
    tmdb_id: Optional[int] = None
    imdb_id: Optional[str] = None
    monitored: bool = True
    media_profile_id: Optional[int] = None
    root_folder_path: Optional[str] = None


class MovieCreate(MovieBase):
    """Schema for creating a movie"""

    pass


class MovieUpdate(BaseModel):
    """Schema for updating a movie"""

    title: Optional[str] = Field(None, max_length=255)
    monitored: Optional[bool] = None
    media_profile_id: Optional[int] = None
    root_folder_path: Optional[str] = None
    status: Optional[str] = None


class Movie(MovieBase):
    """Schema for movie response"""

    id: int
    status: str
    runtime: Optional[int] = None
    budget: Optional[int] = None
    revenue: Optional[int] = None
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
    genres: Optional[List[Dict[str, Any]]] = None
    rating: Optional[float] = None
    vote_count: Optional[int] = None
    popularity: Optional[float] = None
