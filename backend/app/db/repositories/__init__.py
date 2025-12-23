"""
Repository pattern implementations for database access.
"""
from app.db.repositories.base import BaseRepository
from app.db.repositories.movie import MovieRepository
from app.db.repositories.show import ShowRepository, SeasonRepository, EpisodeRepository
from app.db.repositories.anime import AnimeRepository, AnimeEpisodeRepository
from app.db.repositories.music import ArtistRepository, AlbumRepository, TrackRepository
from app.db.repositories.download import DownloadHistoryRepository
from app.db.repositories.profile import MediaProfileRepository
from app.db.repositories.tag import TagRepository, MediaTagRepository

__all__ = [
    "BaseRepository",
    "MovieRepository",
    "ShowRepository",
    "SeasonRepository",
    "EpisodeRepository",
    "AnimeRepository",
    "AnimeEpisodeRepository",
    "ArtistRepository",
    "AlbumRepository",
    "TrackRepository",
    "DownloadHistoryRepository",
    "MediaProfileRepository",
    "TagRepository",
    "MediaTagRepository",
]
