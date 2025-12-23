import os
import shutil
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime


class FileManager:
    """
    File management service for organizing and renaming media files
    Supports custom naming patterns with token replacement
    """

    MOVIE_TOKENS = {
        "{title}": "title",
        "{year}": "year",
        "{quality}": "quality",
        "{source}": "source",
        "{codec}": "codec",
        "{edition}": "edition",
        "{imdb-id}": "imdb_id",
        "{tmdb-id}": "tmdb_id",
    }

    SHOW_TOKENS = {
        "{series}": "series_title",
        "{season:00}": "season_number",
        "{episode:00}": "episode_number",
        "{episode-title}": "episode_title",
        "{quality}": "quality",
        "{source}": "source",
        "{codec}": "codec",
    }

    ANIME_TOKENS = {
        "{title}": "title",
        "{episode:00}": "episode_number",
        "{episode-title}": "episode_title",
        "{quality}": "quality",
        "{source}": "source",
        "{codec}": "codec",
        "{anilist-id}": "anilist_id",
        "{mal-id}": "mal_id",
        "{year}": "year",
    }

    MUSIC_TOKENS = {
        "{artist}": "artist",
        "{album}": "album",
        "{year}": "year",
        "{track:00}": "track_number",
        "{disc:00}": "disc_number",
        "{title}": "title",
        "{genre}": "genre",
        "{format}": "format",
        "{quality}": "quality",
    }

    PRESETS = {
        "plex_movie": "{title} ({year})",
        "plex_show": "{series}/Season {season:00}/{series} - S{season:00}E{episode:00} - {episode-title}",
        "jellyfin_movie": "{title} ({year})",
        "jellyfin_show": "{series}/Season {season:00}/{series} - S{season:00}E{episode:00} - {episode-title}",
    }

    def __init__(self, root_path: str = None):
        self.root_path = Path(root_path) if root_path else None

    def format_movie_filename(
        self,
        pattern: str,
        movie_data: Dict[str, Any],
        include_extension: bool = True,
        illegal_replacement: str = '',
        colon_replacement: str = ' -',
    ) -> str:
        """
        Format movie filename using pattern and tokens
        """
        filename = pattern

        for token, field in self.MOVIE_TOKENS.items():
            value = movie_data.get(field, "")
            if value:
                filename = filename.replace(token, str(value))
            else:
                filename = filename.replace(token, "")

        filename = self._clean_filename(filename, illegal_replacement, colon_replacement)

        if include_extension and "extension" in movie_data:
            filename += movie_data["extension"]

        return filename

    def format_show_filename(
        self,
        pattern: str,
        show_data: Dict[str, Any],
        include_extension: bool = True,
        illegal_replacement: str = '',
        colon_replacement: str = ' -',
    ) -> str:
        """
        Format TV show episode filename using pattern and tokens
        """
        filename = pattern

        for token, field in self.SHOW_TOKENS.items():
            value = show_data.get(field, "")

            # Handle numbered tokens with padding
            if ":00" in token and value:
                filename = filename.replace(token, f"{int(value):02d}")
            elif value:
                filename = filename.replace(token, str(value))
            else:
                filename = filename.replace(token, "")

        filename = self._clean_filename(filename, illegal_replacement, colon_replacement)

        if include_extension and "extension" in show_data:
            filename += show_data["extension"]

        return filename

    def format_anime_filename(
        self,
        pattern: str,
        anime_data: Dict[str, Any],
        include_extension: bool = True,
        illegal_replacement: str = '',
        colon_replacement: str = ' -',
    ) -> str:
        """
        Format anime episode filename using pattern and tokens
        """
        filename = pattern

        for token, field in self.ANIME_TOKENS.items():
            value = anime_data.get(field, "")

            # Handle numbered tokens with padding
            if ":00" in token and value:
                filename = filename.replace(token, f"{int(value):02d}")
            elif value:
                filename = filename.replace(token, str(value))
            else:
                filename = filename.replace(token, "")

        filename = self._clean_filename(filename, illegal_replacement, colon_replacement)

        if include_extension and "extension" in anime_data:
            filename += anime_data["extension"]

        return filename

    def format_music_filename(
        self,
        pattern: str,
        track_data: Dict[str, Any],
        include_extension: bool = True,
        illegal_replacement: str = '',
        colon_replacement: str = ' -',
    ) -> str:
        """
        Format music track filename using pattern and tokens
        """
        filename = pattern

        for token, field in self.MUSIC_TOKENS.items():
            value = track_data.get(field, "")

            # Handle numbered tokens with padding
            if ":00" in token and value:
                filename = filename.replace(token, f"{int(value):02d}")
            elif value:
                filename = filename.replace(token, str(value))
            else:
                filename = filename.replace(token, "")

        filename = self._clean_filename(filename, illegal_replacement, colon_replacement)

        if include_extension and "extension" in track_data:
            filename += track_data["extension"]

        return filename

    def organize_file(
        self,
        source_path: str,
        destination_path: str,
        operation: str = "move",  # move, copy, or hardlink
    ) -> bool:
        """
        Organize file to destination
        Supports move, copy, or hardlink operations
        """
        source = Path(source_path)
        destination = Path(destination_path)

        if not source.exists():
            raise FileNotFoundError(f"Source file not found: {source}")

        # Create destination directory
        destination.parent.mkdir(parents=True, exist_ok=True)

        try:
            if operation == "move":
                shutil.move(str(source), str(destination))
            elif operation == "copy":
                shutil.copy2(str(source), str(destination))
            elif operation == "hardlink":
                if destination.exists():
                    destination.unlink()
                os.link(str(source), str(destination))
            else:
                raise ValueError(f"Invalid operation: {operation}")

            return True

        except Exception as e:
            print(f"Error organizing file: {e}")
            return False

    def extract_largest_video(self, torrent_path: str) -> Optional[str]:
        """
        Extract the largest video file from a torrent download
        Useful for torrents with multiple files
        """
        video_extensions = [".mkv", ".mp4", ".avi", ".m4v", ".mov", ".wmv"]

        path = Path(torrent_path)

        if not path.exists():
            return None

        video_files = []

        if path.is_file():
            if path.suffix.lower() in video_extensions:
                return str(path)
            return None

        # Search directory for video files
        for file in path.rglob("*"):
            if file.is_file() and file.suffix.lower() in video_extensions:
                video_files.append(file)

        if not video_files:
            return None

        # Return largest video file
        largest = max(video_files, key=lambda f: f.stat().st_size)
        return str(largest)

    def extract_all_videos(self, torrent_path: str) -> list[str]:
        """
        Extract all video files from a torrent download.
        Returns list of file paths sorted by name.
        """
        video_extensions = [".mkv", ".mp4", ".avi", ".m4v", ".mov", ".wmv"]
        path = Path(torrent_path)

        if not path.exists():
            return []

        video_files = []

        if path.is_file():
            if path.suffix.lower() in video_extensions:
                return [str(path)]
            return []

        for file in path.rglob("*"):
            if file.is_file() and file.suffix.lower() in video_extensions:
                video_files.append(file)

        # Sort by filename for consistent episode ordering
        video_files.sort(key=lambda f: f.name.lower())
        return [str(f) for f in video_files]

    def extract_all_audio(self, torrent_path: str) -> list[str]:
        """
        Extract all audio files from a torrent download.
        Returns list of file paths sorted by name.
        """
        audio_extensions = [".flac", ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".wma"]
        path = Path(torrent_path)

        if not path.exists():
            return []

        audio_files = []

        if path.is_file():
            if path.suffix.lower() in audio_extensions:
                return [str(path)]
            return []

        for file in path.rglob("*"):
            if file.is_file() and file.suffix.lower() in audio_extensions:
                audio_files.append(file)

        # Sort by filename for consistent track ordering
        audio_files.sort(key=lambda f: f.name.lower())
        return [str(f) for f in audio_files]

    def get_file_quality(self, filename: str) -> Dict[str, Optional[str]]:
        """
        Extract quality information from filename
        """
        from app.services.indexers.base import BaseIndexer

        indexer = BaseIndexer()
        return indexer.parse_quality(filename)

    def _clean_filename(
        self,
        filename: str,
        illegal_replacement: str = '',
        colon_replacement: str = ' -'
    ) -> str:
        """
        Clean filename by replacing invalid characters.

        Args:
            filename: The filename to clean
            illegal_replacement: String to replace illegal chars with (default: remove)
            colon_replacement: String to replace colons with (default: ' -')
        """
        # Handle colons separately with custom replacement
        filename = filename.replace(':', colon_replacement)

        # Replace other invalid characters
        invalid_chars = ['<', '>', '"', '/', '\\', '|', '?', '*']
        for char in invalid_chars:
            filename = filename.replace(char, illegal_replacement)

        # Replace multiple spaces with single space
        filename = ' '.join(filename.split())

        # Remove leading/trailing spaces
        filename = filename.strip()

        return filename

    def get_disk_space(self, path: str) -> Dict[str, int]:
        """
        Get disk space information for path
        """
        stat = shutil.disk_usage(path)

        return {
            "total": stat.total,
            "used": stat.used,
            "free": stat.free,
            "percent_used": (stat.used / stat.total) * 100,
        }

    def has_sufficient_space(
        self, path: str, required_bytes: int, buffer_gb: int = 5
    ) -> bool:
        """
        Check if path has sufficient disk space
        Includes buffer for safety
        """
        buffer_bytes = buffer_gb * 1024 * 1024 * 1024
        space = self.get_disk_space(path)

        return space["free"] > (required_bytes + buffer_bytes)


def create_file_manager(root_path: Optional[str] = None) -> FileManager:
    """
    Factory function to create FileManager with config
    """
    from app.core.config import settings

    path = root_path or settings.MEDIA_ROOT
    return FileManager(path)
