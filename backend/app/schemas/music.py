from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ArtistBase(BaseModel):
    """Base artist schema"""

    name: str = Field(..., max_length=255)
    picture: Optional[str] = None
    picture_medium: Optional[str] = None
    picture_big: Optional[str] = None
    picture_xl: Optional[str] = None
    deezer_id: Optional[int] = None
    monitored: bool = True
    root_folder_id: Optional[int] = None


class ArtistCreate(ArtistBase):
    """Schema for creating an artist"""

    nb_album: Optional[int] = None
    nb_fan: Optional[int] = None
    media_profile_id: Optional[int] = None


class ArtistUpdate(BaseModel):
    """Schema for updating an artist"""

    name: Optional[str] = Field(None, max_length=255)
    monitored: Optional[bool] = None
    upgrade_allowed: Optional[bool] = None
    root_folder_id: Optional[int] = None


class Artist(ArtistBase):
    """Schema for artist response"""

    id: int
    genres: Optional[List[Dict[str, Any]]] = None
    nb_album: Optional[int] = None
    nb_fan: Optional[int] = None
    has_files: bool = False
    upgrade_allowed: Optional[bool] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ArtistSearch(BaseModel):
    """Schema for artist search response from Deezer"""

    deezer_id: int
    name: str
    picture: Optional[str] = None
    picture_medium: Optional[str] = None
    picture_big: Optional[str] = None
    picture_xl: Optional[str] = None
    nb_album: Optional[int] = None
    nb_fan: Optional[int] = None


class AlbumBase(BaseModel):
    """Base album schema"""

    title: str = Field(..., max_length=255)
    cover: Optional[str] = None
    cover_medium: Optional[str] = None
    cover_big: Optional[str] = None
    cover_xl: Optional[str] = None
    release_date: Optional[datetime] = None
    deezer_id: Optional[int] = None
    artist_id: Optional[int] = None
    upc: Optional[str] = None
    monitored: bool = True
    media_profile_id: Optional[int] = None
    root_folder_id: Optional[int] = None


class AlbumCreate(AlbumBase):
    """Schema for creating an album"""

    nb_tracks: Optional[int] = None
    artist_name: Optional[str] = None
    explicit_lyrics: Optional[bool] = False
    record_type: Optional[str] = None


class AlbumUpdate(BaseModel):
    """Schema for updating an album"""

    title: Optional[str] = Field(None, max_length=255)
    monitored: Optional[bool] = None
    media_profile_id: Optional[int] = None
    root_folder_id: Optional[int] = None
    status: Optional[str] = None


class Album(AlbumBase):
    """Schema for album response"""

    id: int
    status: str
    genres: Optional[List[Dict[str, Any]]] = None
    nb_tracks: Optional[int] = None
    duration: Optional[int] = None
    label: Optional[str] = None
    explicit_lyrics: Optional[bool] = False
    record_type: Optional[str] = None
    artist_name: Optional[str] = None
    has_file: bool = False
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    quality_detected: Optional[str] = None
    codec: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AlbumSearch(BaseModel):
    """Schema for album search response from Deezer"""

    deezer_id: int
    title: str
    cover: Optional[str] = None
    cover_medium: Optional[str] = None
    cover_big: Optional[str] = None
    cover_xl: Optional[str] = None
    release_date: Optional[str] = None
    nb_tracks: Optional[int] = None
    explicit_lyrics: Optional[bool] = False
    record_type: Optional[str] = None
    artist: Optional[Dict[str, Any]] = None
    genres: Optional[List[Dict[str, Any]]] = None


class TrackBase(BaseModel):
    """Base track schema"""

    title: str = Field(..., max_length=255)
    duration: Optional[int] = None
    track_position: Optional[int] = None
    disk_number: Optional[int] = None
    deezer_id: Optional[int] = None
    album_id: Optional[int] = None
    isrc: Optional[str] = None
    monitored: bool = True


class TrackCreate(TrackBase):
    """Schema for creating a track"""

    explicit_lyrics: Optional[bool] = False
    preview: Optional[str] = None
    artist_name: Optional[str] = None
    album_title: Optional[str] = None
    media_profile_id: Optional[int] = None


class TrackUpdate(BaseModel):
    """Schema for updating a track"""

    title: Optional[str] = Field(None, max_length=255)
    monitored: Optional[bool] = None
    upgrade_allowed: Optional[bool] = None


class Track(TrackBase):
    """Schema for track response"""

    id: int
    explicit_lyrics: Optional[bool] = False
    preview: Optional[str] = None
    artist_name: Optional[str] = None
    album_title: Optional[str] = None
    album_cover: Optional[str] = None
    album_cover_medium: Optional[str] = None
    album_cover_big: Optional[str] = None
    album_cover_xl: Optional[str] = None
    album_release_date: Optional[datetime] = None
    has_file: bool = False
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    upgrade_allowed: Optional[bool] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TrackSearch(BaseModel):
    """Schema for track search response from Deezer"""

    deezer_id: int
    title: str
    duration: Optional[int] = None
    track_position: Optional[int] = None
    disk_number: Optional[int] = None
    explicit_lyrics: Optional[bool] = False
    preview: Optional[str] = None
    artist: Optional[Dict[str, Any]] = None
    album: Optional[Dict[str, Any]] = None
