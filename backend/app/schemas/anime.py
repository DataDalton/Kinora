from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class AnimeBase(BaseModel):
    """Base anime schema"""

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
    anilist_id: Optional[int] = None
    mal_id: Optional[int] = None
    tmdb_id: Optional[int] = None
    imdb_id: Optional[str] = None
    monitored: bool = True
    media_profile_id: Optional[int] = None
    root_folder_path: Optional[str] = None
    absolute_numbering: bool = True
    episode_monitoring: str = "all"


class AnimeCreate(AnimeBase):
    """Schema for creating anime"""

    pass


class AnimeUpdate(BaseModel):
    """Schema for updating anime"""

    title: Optional[str] = Field(None, max_length=255)
    monitored: Optional[bool] = None
    media_profile_id: Optional[int] = None
    root_folder_path: Optional[str] = None
    episode_monitoring: Optional[str] = None
    status: Optional[str] = None


class Anime(AnimeBase):
    """Schema for anime response"""

    id: int
    status: str
    episodes: Optional[int] = None
    duration: Optional[int] = None
    season_year: Optional[int] = None
    season_period: Optional[str] = None
    format: Optional[str] = None
    source: Optional[str] = None
    studios: Optional[List[Dict[str, Any]]] = None
    is_adult: bool = False
    has_file: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
