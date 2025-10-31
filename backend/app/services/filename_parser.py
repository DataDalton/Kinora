"""
Filename parser for extracting metadata from media filenames.
Used as fallback when file metadata extraction fails.
"""

import re
from typing import Optional, Dict, Any
from pathlib import Path


class FilenameParser:
    """Parses media filenames to extract title, year, season, episode, quality."""

    VIDEO_EXTENSIONS = {
        '.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.m4v',
        '.mpg', '.mpeg', '.m2ts', '.ts', '.webm'
    }

    def parse_movie(self, filename: str) -> Dict[str, Any]:
        """
        Parse movie filename to extract metadata.

        Examples:
          - "The Matrix (1999) 1080p BluRay x264.mkv"
          - "Inception.2010.2160p.WEB-DL.x265.mkv"
          - "Fight Club 1999 Directors Cut 1080p.mkv"
        """
        result = {
            'title': None,
            'year': None,
            'original_filename': filename
        }

        name = Path(filename).stem

        # Extract year (4 digits, typically 1900-2099)
        year_match = re.search(r'[\(\[\.\s](\d{4})[\)\]\.\s]', name)
        if year_match:
            result['year'] = int(year_match.group(1))
            year_pos = year_match.start(1)
            title_part = name[:year_pos].strip()
        else:
            # No year, try to split at quality indicators
            quality_split = re.search(r'[\.\s](1080p|720p|2160p|4K)', name, re.IGNORECASE)
            if quality_split:
                title_part = name[:quality_split.start()].strip()
            else:
                title_part = name

        # Clean title: replace dots/underscores with spaces
        title = title_part.replace('.', ' ').replace('_', ' ')
        title = re.sub(r'\s+', ' ', title).strip()
        # Remove common prefixes like [GroupName]
        title = re.sub(r'^\[.*?\]\s*', '', title)
        result['title'] = title

        return result

    def parse_show(self, filename: str) -> Dict[str, Any]:
        """
        Parse TV show filename to extract metadata.

        Examples:
          - "Breaking Bad S01E01 Pilot 1080p.mkv"
          - "Game.of.Thrones.S08E06.1080p.WEB-DL.mkv"
          - "The Office (US) - s02e05 - Halloween.mkv"
          - "Friends 1x01 The One Where It All Began.mkv"
        """
        result = {
            'title': None,
            'season': None,
            'episode': None,
            'episode_title': None,
            'original_filename': filename
        }

        name = Path(filename).stem

        # Try various season/episode patterns
        # Pattern 1: S01E01 or s01e01
        se_match = re.search(r'[Ss](\d{1,2})[Ee](\d{1,2})', name)
        if se_match:
            result['season'] = int(se_match.group(1))
            result['episode'] = int(se_match.group(2))
            title_part = name[:se_match.start()].strip()
            quality_part = name[se_match.end():]
        else:
            # Pattern 2: 1x01 or 1×01
            x_match = re.search(r'(\d{1,2})[x×](\d{1,2})', name)
            if x_match:
                result['season'] = int(x_match.group(1))
                result['episode'] = int(x_match.group(2))
                title_part = name[:x_match.start()].strip()
                quality_part = name[x_match.end():]
            else:
                # Pattern 3: Season 1 Episode 1
                season_ep_match = re.search(r'Season\s*(\d+)\s*Episode\s*(\d+)', name, re.IGNORECASE)
                if season_ep_match:
                    result['season'] = int(season_ep_match.group(1))
                    result['episode'] = int(season_ep_match.group(2))
                    title_part = name[:season_ep_match.start()].strip()
                    quality_part = name[season_ep_match.end():]
                else:
                    title_part = name
                    quality_part = ''

        # Clean title
        title = title_part.replace('.', ' ').replace('_', ' ')
        # Remove year in parentheses
        title = re.sub(r'\s*\(\d{4}\)\s*', ' ', title)
        title = re.sub(r'\s+', ' ', title).strip()
        # Remove common prefixes
        title = re.sub(r'^\[.*?\]\s*', '', title)
        # Remove trailing hyphens
        title = re.sub(r'\s*[-–—]\s*$', '', title).strip()
        result['title'] = title

        # Extract episode title if present
        if result['season'] and result['episode']:
            ep_title_match = re.search(r'[-–—]\s*([^-–—]+?)(?:\s*[-–—]\s*|\s+(?:1080p|720p|2160p|WEB|BluRay))', quality_part, re.IGNORECASE)
            if ep_title_match:
                ep_title = ep_title_match.group(1).replace('.', ' ').strip()
                ep_title = re.sub(r'\s+', ' ', ep_title)
                result['episode_title'] = ep_title

        return result

    def parse_anime(self, filename: str) -> Dict[str, Any]:
        """
        Parse anime filename to extract metadata.

        Examples:
          - "[SubsPlease] Demon Slayer - 01 (1080p).mkv"
          - "Attack on Titan S04E16 1080p.mkv"
          - "One Piece - 1000 [1080p].mkv"
          - "[HorribleSubs] My Hero Academia - S02E01.mkv"
        """
        result = {
            'title': None,
            'season': None,
            'episode': None,
            'release_group': None,
            'original_filename': filename
        }

        name = Path(filename).stem

        # Extract release group from brackets at start
        group_match = re.match(r'^\[([^\]]+)\]\s*', name)
        if group_match:
            result['release_group'] = group_match.group(1)
            name = name[group_match.end():]

        # Try seasonal format first (S01E01)
        se_match = re.search(r'[Ss](\d{1,2})[Ee](\d{1,2})', name)
        if se_match:
            result['season'] = int(se_match.group(1))
            result['episode'] = int(se_match.group(2))
            title_part = name[:se_match.start()].strip()
        else:
            # Try numbered episode format (- 01 or Episode 01)
            ep_match = re.search(r'[-–—]\s*(\d{1,4})(?:\s|\.|\[)', name)
            if ep_match:
                result['episode'] = int(ep_match.group(1))
                title_part = name[:ep_match.start()].strip()
            else:
                # Try Episode keyword
                episode_kw = re.search(r'Episode\s*(\d+)', name, re.IGNORECASE)
                if episode_kw:
                    result['episode'] = int(episode_kw.group(1))
                    title_part = name[:episode_kw.start()].strip()
                else:
                    title_part = name

        # Clean title
        title = title_part.replace('.', ' ').replace('_', ' ')
        title = re.sub(r'\s+', ' ', title).strip()
        title = re.sub(r'\s*[-–—]\s*$', '', title).strip()
        result['title'] = title

        return result

    def is_video_file(self, filename: str) -> bool:
        """Check if filename has a video extension."""
        return Path(filename).suffix.lower() in self.VIDEO_EXTENSIONS

    def is_sample(self, filename: str) -> bool:
        """Check if file appears to be a sample/trailer."""
        name_lower = filename.lower()
        return any(indicator in name_lower for indicator in ['sample', 'trailer', 'preview', 'rarbg'])

    def detect_media_type(self, filename: str) -> str:
        """
        Detect media type from filename patterns.
        Returns 'movie', 'show', or 'unknown'.
        """
        name = filename.lower()

        # Check for show indicators
        if re.search(r's\d{1,2}e\d{1,2}', name):
            return 'show'
        if re.search(r'\d{1,2}x\d{1,2}', name):
            return 'show'
        if re.search(r'season\s*\d+', name):
            return 'show'

        # Check for movie indicators
        if re.search(r'\(\d{4}\)', name):
            return 'movie'

        return 'unknown'
