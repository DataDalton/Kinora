"""
Library scanner service for importing existing media files.
Recursively scans directories, extracts metadata, and prepares files for import.
"""

import os
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging

from app.services.metadata_extractor import MetadataExtractor
from app.services.filename_parser import FilenameParser


logger = logging.getLogger(__name__)


class LibraryScanner:
    """Scans directories for media files and extracts metadata."""

    def __init__(self, ffprobe_path: str = 'ffprobe'):
        self.metadata_extractor = MetadataExtractor(ffprobe_path)
        self.filename_parser = FilenameParser()

    def scan_directory(
        self,
        directory_path: str,
        media_type: str,
        recursive: bool = True,
        skip_samples: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Scan directory for media files and extract metadata.

        Args:
            directory_path: Path to directory to scan
            media_type: 'movie', 'show', or 'anime'
            recursive: Whether to scan subdirectories
            skip_samples: Whether to skip sample/trailer files

        Returns:
            List of scanned file metadata dictionaries
        """
        if not os.path.exists(directory_path):
            raise ValueError(f"Directory does not exist: {directory_path}")

        if not os.path.isdir(directory_path):
            raise ValueError(f"Path is not a directory: {directory_path}")

        logger.info(f"Starting scan of {directory_path} for {media_type}")

        scanned_files = []

        if recursive:
            for root, dirs, files in os.walk(directory_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    file_metadata = self._scan_file(file_path, media_type, skip_samples)
                    if file_metadata:
                        scanned_files.append(file_metadata)
        else:
            for item in os.listdir(directory_path):
                file_path = os.path.join(directory_path, item)
                if os.path.isfile(file_path):
                    file_metadata = self._scan_file(file_path, media_type, skip_samples)
                    if file_metadata:
                        scanned_files.append(file_metadata)

        logger.info(f"Scan complete. Found {len(scanned_files)} media files")
        return scanned_files

    def _scan_file(
        self,
        file_path: str,
        media_type: str,
        skip_samples: bool
    ) -> Optional[Dict[str, Any]]:
        """
        Scan individual file and extract metadata.

        Returns:
            Metadata dictionary or None if file should be skipped
        """
        # Check if it's a video file
        if not self.metadata_extractor.is_video_file(file_path):
            return None

        # Skip samples if requested
        if skip_samples and self.metadata_extractor.is_sample(file_path):
            logger.debug(f"Skipping sample file: {file_path}")
            return None

        # Extract file metadata using ffprobe
        file_metadata = self.metadata_extractor.extract_metadata(file_path)

        # Parse filename as fallback
        filename = os.path.basename(file_path)
        if media_type == 'movie':
            filename_metadata = self.filename_parser.parse_movie(filename)
        elif media_type == 'show':
            filename_metadata = self.filename_parser.parse_show(filename)
        elif media_type == 'anime':
            filename_metadata = self.filename_parser.parse_anime(filename)
        else:
            filename_metadata = {}

        # Merge metadata: prefer file metadata, fallback to filename
        combined_metadata = {
            'file_path': file_path,
            'file_name': filename,
            'media_type': media_type,
        }

        # Title: prefer embedded title, fallback to filename
        combined_metadata['title'] = (
            file_metadata.get('title') if file_metadata else None
        ) or filename_metadata.get('title')

        # Year: prefer embedded year, fallback to filename
        combined_metadata['year'] = (
            file_metadata.get('year') if file_metadata else None
        ) or filename_metadata.get('year')

        # For shows/anime, get season/episode from filename (rarely in file metadata)
        if media_type in ['show', 'anime']:
            combined_metadata['season'] = filename_metadata.get('season')
            combined_metadata['episode'] = filename_metadata.get('episode')
            combined_metadata['episode_title'] = filename_metadata.get('episode_title')

        # For anime, include release group
        if media_type == 'anime':
            combined_metadata['release_group'] = filename_metadata.get('release_group')

        # Technical metadata from file
        if file_metadata:
            combined_metadata['file_size'] = file_metadata.get('file_size')
            combined_metadata['duration'] = file_metadata.get('duration')
            combined_metadata['quality'] = file_metadata.get('quality')
            combined_metadata['video'] = file_metadata.get('video')
            combined_metadata['audio'] = file_metadata.get('audio')
            combined_metadata['subtitles'] = file_metadata.get('subtitles')
            combined_metadata['format_name'] = file_metadata.get('format_name')

        logger.debug(f"Scanned: {filename} -> Title: {combined_metadata.get('title')}, Year: {combined_metadata.get('year')}")

        return combined_metadata

    def scan_single_file(self, file_path: str, media_type: str) -> Optional[Dict[str, Any]]:
        """
        Scan a single file and extract metadata.

        Args:
            file_path: Path to file
            media_type: 'movie', 'show', or 'anime'

        Returns:
            Metadata dictionary or None if invalid
        """
        if not os.path.exists(file_path):
            raise ValueError(f"File does not exist: {file_path}")

        if not os.path.isfile(file_path):
            raise ValueError(f"Path is not a file: {file_path}")

        return self._scan_file(file_path, media_type, skip_samples=False)

    def group_show_episodes(self, scanned_files: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Group scanned show files by series title.

        Args:
            scanned_files: List of scanned file metadata

        Returns:
            Dictionary mapping series titles to lists of episode files
        """
        grouped = {}

        for file_metadata in scanned_files:
            title = file_metadata.get('title')
            if not title:
                continue

            # Normalize title for grouping
            normalized_title = title.lower().strip()

            if normalized_title not in grouped:
                grouped[normalized_title] = []

            grouped[normalized_title].append(file_metadata)

        # Sort episodes within each series
        for title, episodes in grouped.items():
            episodes.sort(key=lambda x: (
                x.get('season') or 0,
                x.get('episode') or 0
            ))

        return grouped

    def estimate_scan_time(self, directory_path: str) -> Dict[str, Any]:
        """
        Estimate scan time by counting files in directory.

        Args:
            directory_path: Path to directory

        Returns:
            Dictionary with file count and estimated time
        """
        if not os.path.exists(directory_path):
            raise ValueError(f"Directory does not exist: {directory_path}")

        video_count = 0

        for root, dirs, files in os.walk(directory_path):
            for file in files:
                if self.metadata_extractor.is_video_file(file):
                    video_count += 1

        # Estimate: ~0.1 seconds per file for ffprobe
        estimated_seconds = video_count * 0.1

        return {
            'video_file_count': video_count,
            'estimated_seconds': estimated_seconds,
            'estimated_minutes': round(estimated_seconds / 60, 1)
        }
