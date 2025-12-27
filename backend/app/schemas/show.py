from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class EpisodeBase(BaseModel):
    """Base episode schema"""

    episode_number: int
    name: Optional[str] = None
    overview: Optional[str] = None
    still_path: Optional[str] = None
    air_date: Optional[datetime] = None
    runtime: Optional[int] = None
    monitored: bool = True


class Episode(EpisodeBase):
    """Schema for episode response"""

    id: int
    season_id: int
    has_file: bool
    file_path: Optional[str] = None
    quality_detected: Optional[str] = None
    tmdb_id: Optional[int] = None

    class Config:
        from_attributes = True


class SeasonBase(BaseModel):
    """Base season schema"""

    season_number: int
    name: Optional[str] = None
    overview: Optional[str] = None
    poster_path: Optional[str] = None
    air_date: Optional[datetime] = None
    episode_count: Optional[int] = None
    monitored: bool = True


class Season(SeasonBase):
    """Schema for season response"""

    id: int
    show_id: int
    tmdb_id: Optional[int] = None
    episodes: Optional[List[Episode]] = []

    class Config:
        from_attributes = True


class ShowBase(BaseModel):
    """Base show schema"""

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
    tvdb_id: Optional[int] = None
    monitored: bool = True
    media_profile_id: Optional[int] = None
    root_folder_id: Optional[int] = None
    season_monitoring: str = "all"


class ShowCreate(ShowBase):
    """Schema for creating a show"""

    pass


class ShowUpdate(BaseModel):
    """Schema for updating a show"""

    title: Optional[str] = Field(None, max_length=255)
    monitored: Optional[bool] = None
    media_profile_id: Optional[int] = None
    root_folder_id: Optional[int] = None
    season_monitoring: Optional[str] = None
    status: Optional[str] = None


class Show(ShowBase):
    """Schema for show response"""

    id: int
    status: str
    number_of_seasons: Optional[int] = None
    number_of_episodes: Optional[int] = None
    networks: Optional[List[Dict[str, Any]]] = None
    first_air_date: Optional[datetime] = None
    last_air_date: Optional[datetime] = None
    in_production: bool = False
    created_at: datetime
    updated_at: datetime
    seasons: Optional[List[Season]] = []

    class Config:
        from_attributes = True
