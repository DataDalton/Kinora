"""
Media matcher service for identifying scanned files using TMDB and Anilist.
Performs fuzzy matching to associate files with metadata.
"""

from typing import Optional, Dict, Any, List
import logging
from difflib import SequenceMatcher

from app.services.metadata.tmdb import TMDBService
from app.services.metadata.anilist import AnilistService


logger = logging.getLogger(__name__)


class MediaMatcher:
    """Matches scanned files to TMDB/Anilist metadata."""

    def __init__(self):
        self.tmdb = TMDBService()
        self.anilist = AnilistService()

    def match_movie(
        self,
        title: str,
        year: Optional[int] = None,
        similarity_threshold: float = 0.7
    ) -> Optional[Dict[str, Any]]:
        """
        Match movie title to TMDB entry.

        Args:
            title: Movie title from file
            year: Release year (optional but improves accuracy)
            similarity_threshold: Minimum similarity score (0-1)

        Returns:
            TMDB movie data or None if no match found
        """
        if not title:
            return None

        try:
            # Search TMDB
            results = self.tmdb.search_movie(title, year=year)

            if not results:
                # Try without year if initial search failed
                if year:
                    results = self.tmdb.search_movie(title)

            if not results:
                logger.debug(f"No TMDB results for: {title} ({year})")
                return None

            # Find best match using fuzzy matching
            best_match = None
            best_score = 0

            for result in results[:10]:  # Check top 10 results
                result_title = result.get('title', '').lower()
                result_year = result.get('release_date', '')[:4] if result.get('release_date') else None

                # Calculate title similarity
                title_score = self._calculate_similarity(title.lower(), result_title)

                # Year match bonus
                year_bonus = 0.1 if year and result_year and str(year) == result_year else 0

                total_score = title_score + year_bonus

                if total_score > best_score:
                    best_score = total_score
                    best_match = result

            if best_score >= similarity_threshold:
                logger.info(f"Matched movie: {title} -> {best_match.get('title')} (score: {best_score:.2f})")
                # Get full movie details
                return self.tmdb.get_movie(best_match['id'])
            else:
                logger.debug(f"No confident match for: {title} (best score: {best_score:.2f})")
                return None

        except Exception as e:
            logger.error(f"Error matching movie {title}: {e}")
            return None

    def match_show(
        self,
        title: str,
        year: Optional[int] = None,
        similarity_threshold: float = 0.7
    ) -> Optional[Dict[str, Any]]:
        """
        Match TV show title to TMDB entry.

        Args:
            title: Show title from file
            year: First air year (optional)
            similarity_threshold: Minimum similarity score (0-1)

        Returns:
            TMDB show data or None if no match found
        """
        if not title:
            return None

        try:
            # Search TMDB
            results = self.tmdb.search_tv(title, year=year)

            if not results:
                # Try without year
                if year:
                    results = self.tmdb.search_tv(title)

            if not results:
                logger.debug(f"No TMDB results for show: {title} ({year})")
                return None

            # Find best match
            best_match = None
            best_score = 0

            for result in results[:10]:
                result_title = result.get('name', '').lower()
                result_year = result.get('first_air_date', '')[:4] if result.get('first_air_date') else None

                title_score = self._calculate_similarity(title.lower(), result_title)
                year_bonus = 0.1 if year and result_year and str(year) == result_year else 0

                total_score = title_score + year_bonus

                if total_score > best_score:
                    best_score = total_score
                    best_match = result

            if best_score >= similarity_threshold:
                logger.info(f"Matched show: {title} -> {best_match.get('name')} (score: {best_score:.2f})")
                # Get full show details
                return self.tmdb.get_tv(best_match['id'])
            else:
                logger.debug(f"No confident match for show: {title} (best score: {best_score:.2f})")
                return None

        except Exception as e:
            logger.error(f"Error matching show {title}: {e}")
            return None

    def match_anime(
        self,
        title: str,
        year: Optional[int] = None,
        similarity_threshold: float = 0.7
    ) -> Optional[Dict[str, Any]]:
        """
        Match anime title to Anilist entry.

        Args:
            title: Anime title from file
            year: Release year (optional)
            similarity_threshold: Minimum similarity score (0-1)

        Returns:
            Anilist anime data or None if no match found
        """
        if not title:
            return None

        try:
            # Search Anilist
            results = self.anilist.search_anime(title, year=year)

            if not results:
                # Try without year
                if year:
                    results = self.anilist.search_anime(title)

            if not results:
                logger.debug(f"No Anilist results for: {title} ({year})")
                return None

            # Find best match using fuzzy matching
            best_match = None
            best_score = 0

            for result in results[:10]:
                # Check multiple title variations
                result_titles = [
                    result.get('title_english', ''),
                    result.get('title_romaji', ''),
                    result.get('title_native', '')
                ]

                # Calculate max similarity across all title variations
                max_title_score = 0
                for result_title in result_titles:
                    if result_title:
                        score = self._calculate_similarity(title.lower(), result_title.lower())
                        max_title_score = max(max_title_score, score)

                result_year = result.get('season_year')
                year_bonus = 0.1 if year and result_year and year == result_year else 0

                total_score = max_title_score + year_bonus

                if total_score > best_score:
                    best_score = total_score
                    best_match = result

            if best_score >= similarity_threshold:
                display_title = best_match.get('title_english') or best_match.get('title_romaji')
                logger.info(f"Matched anime: {title} -> {display_title} (score: {best_score:.2f})")
                # Get full anime details
                return self.anilist.get_anime(best_match['id'])
            else:
                logger.debug(f"No confident match for anime: {title} (best score: {best_score:.2f})")
                return None

        except Exception as e:
            logger.error(f"Error matching anime {title}: {e}")
            return None

    def match_scanned_file(
        self,
        file_metadata: Dict[str, Any],
        similarity_threshold: float = 0.7
    ) -> Optional[Dict[str, Any]]:
        """
        Match a scanned file to appropriate metadata service.

        Args:
            file_metadata: Scanned file metadata from LibraryScanner
            similarity_threshold: Minimum similarity score

        Returns:
            Matched metadata with additional 'match_confidence' field
        """
        media_type = file_metadata.get('media_type')
        title = file_metadata.get('title')
        year = file_metadata.get('year')

        if not title:
            logger.warning(f"No title found for file: {file_metadata.get('file_name')}")
            return None

        matched_data = None

        if media_type == 'movie':
            matched_data = self.match_movie(title, year, similarity_threshold)
        elif media_type == 'show':
            matched_data = self.match_show(title, year, similarity_threshold)
        elif media_type == 'anime':
            matched_data = self.match_anime(title, year, similarity_threshold)

        if matched_data:
            # Merge file metadata with matched metadata
            matched_data['scanned_file'] = file_metadata
            return matched_data

        return None

    def batch_match_files(
        self,
        scanned_files: List[Dict[str, Any]],
        similarity_threshold: float = 0.7
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Match multiple scanned files to metadata.

        Args:
            scanned_files: List of scanned file metadata
            similarity_threshold: Minimum similarity score

        Returns:
            Dictionary with 'matched' and 'unmatched' file lists
        """
        matched = []
        unmatched = []

        for file_metadata in scanned_files:
            matched_data = self.match_scanned_file(file_metadata, similarity_threshold)

            if matched_data:
                matched.append(matched_data)
            else:
                unmatched.append(file_metadata)

        logger.info(f"Batch match complete: {len(matched)} matched, {len(unmatched)} unmatched")

        return {
            'matched': matched,
            'unmatched': unmatched
        }

    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """
        Calculate similarity score between two strings.

        Uses SequenceMatcher for fuzzy matching.

        Returns:
            Similarity score between 0 and 1
        """
        if not str1 or not str2:
            return 0.0

        # Remove common words that might interfere with matching
        ignore_words = ['the', 'a', 'an']

        def clean_string(s: str) -> str:
            words = s.lower().split()
            words = [w for w in words if w not in ignore_words]
            return ' '.join(words)

        cleaned_str1 = clean_string(str1)
        cleaned_str2 = clean_string(str2)

        return SequenceMatcher(None, cleaned_str1, cleaned_str2).ratio()
