"""
Movie repository with tag-aware queries and batch operations.
"""
from typing import List, Optional, Dict, Any
import asyncpg

from app.db.repositories.base import BaseRepository
from app.schemas.movie import Movie


class MovieRepository(BaseRepository[Movie]):
    """Repository for movie database operations."""

    tableName = "movies"
    modelClass = Movie

    async def listWithTags(
        self,
        limit: int = 100,
        offset: int = 0,
        monitoredOnly: bool = False,
    ) -> Dict[str, Any]:
        """Fetch movies with their tags in a single query using JSON aggregation."""
        whereClause = "WHERE m.monitored = TRUE" if monitoredOnly else ""

        query = f"""
            SELECT m.*,
                   COALESCE(
                       json_agg(
                           json_build_object('id', t.id, 'name', t.name, 'color', t.color)
                       ) FILTER (WHERE t.id IS NOT NULL),
                       '[]'::json
                   ) as tags
            FROM movies m
            LEFT JOIN media_tags mt ON m.id = mt.media_id AND mt.media_type = 'movie'
            LEFT JOIN tags t ON mt.tag_id = t.id
            {whereClause}
            GROUP BY m.id
            ORDER BY m.created_at DESC
            LIMIT $1 OFFSET $2
        """

        # Get total count of all movies in database
        total = await self.conn.fetchval("SELECT COUNT(*) FROM movies")

        rows = await self.conn.fetch(query, limit, offset)
        movies = [dict(row) for row in rows]
        return {"movies": movies, "total": total}

    async def getWithTags(self, movieId: int) -> Optional[Dict[str, Any]]:
        """Fetch a single movie with its tags."""
        query = """
            SELECT m.*,
                   COALESCE(
                       json_agg(
                           json_build_object('id', t.id, 'name', t.name, 'color', t.color)
                       ) FILTER (WHERE t.id IS NOT NULL),
                       '[]'::json
                   ) as tags
            FROM movies m
            LEFT JOIN media_tags mt ON m.id = mt.media_id AND mt.media_type = 'movie'
            LEFT JOIN tags t ON mt.tag_id = t.id
            WHERE m.id = $1
            GROUP BY m.id
        """
        row = await self.conn.fetchrow(query, movieId)
        return dict(row) if row else None

    async def getByTmdbId(self, tmdbId: int) -> Optional[Movie]:
        """Find a movie by TMDB ID."""
        return await self.findOneBy("tmdb_id", tmdbId)

    async def getByImdbId(self, imdbId: str) -> Optional[Movie]:
        """Find a movie by IMDB ID."""
        return await self.findOneBy("imdb_id", imdbId)

    async def existsByTmdbId(self, tmdbId: int) -> bool:
        """Check if a movie with the given TMDB ID exists."""
        result = await self.conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM movies WHERE tmdb_id = $1)", tmdbId
        )
        return result

    async def getWanted(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get movies with status 'wanted' and monitored=true for wanted search."""
        rows = await self.conn.fetch(
            """
            SELECT m.*, mp.name as profile_name
            FROM movies m
            LEFT JOIN media_profiles mp ON m.media_profile_id = mp.id
            WHERE m.status = 'wanted' AND m.monitored = TRUE
            ORDER BY m.created_at DESC
            LIMIT $1
            """,
            limit
        )
        return [dict(row) for row in rows]

    async def updateStatus(self, movieId: int, status: str) -> Optional[Movie]:
        """Update movie status."""
        return await self.update(movieId, {"status": status})

    async def updateStatusBatch(self, ids: List[int], status: str) -> int:
        """Batch update status for multiple movies."""
        return await self.updateBatch(ids, {"status": status})

    async def updateMonitoredBatch(self, ids: List[int], monitored: bool) -> int:
        """Batch update monitored flag for multiple movies."""
        return await self.updateBatch(ids, {"monitored": monitored})

    async def updateFileInfo(
        self,
        movieId: int,
        hasFile: bool,
        filePath: Optional[str] = None,
        fileSize: Optional[int] = None,
        qualityDetected: Optional[str] = None,
        codec: Optional[str] = None,
        resolution: Optional[str] = None,
    ) -> Optional[Movie]:
        """Update file-related fields for a movie."""
        data = {
            "has_file": hasFile,
            "file_path": filePath,
            "file_size": fileSize,
            "quality_detected": qualityDetected,
            "codec": codec,
            "resolution": resolution,
        }
        # Remove None values
        data = {k: v for k, v in data.items() if v is not None or k == "has_file"}
        return await self.update(movieId, data)

    async def refreshMetadata(self, movieId: int, metadata: Dict[str, Any]) -> Optional[Movie]:
        """Update movie with fresh metadata from TMDB."""
        return await self.update(movieId, metadata)

    async def searchFullText(self, query: str, limit: int = 20) -> List[Movie]:
        """Full-text search on movie titles."""
        rows = await self.conn.fetch(
            """
            SELECT * FROM movies
            WHERE to_tsvector('english', title) @@ plainto_tsquery('english', $1)
            ORDER BY ts_rank(to_tsvector('english', title), plainto_tsquery('english', $1)) DESC
            LIMIT $2
            """,
            query, limit
        )
        return [self.modelClass(**dict(row)) for row in rows]

    async def deleteWithRelations(self, movieId: int) -> bool:
        """Delete a movie and all related records (tags, history, blocklist)."""
        # These could be done in a transaction, but CASCADE on FK handles some
        await self.conn.execute(
            "DELETE FROM download_history WHERE media_type = 'movie' AND media_id = $1",
            movieId
        )
        await self.conn.execute(
            "DELETE FROM blocklist WHERE media_type = 'movie' AND media_id = $1",
            movieId
        )
        await self.conn.execute(
            "DELETE FROM media_tags WHERE media_type = 'movie' AND media_id = $1",
            movieId
        )
        return await self.delete(movieId)

    async def getStats(self) -> Dict[str, Any]:
        """Get movie statistics."""
        stats = await self.conn.fetchrow(
            """
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE monitored = TRUE) as monitored,
                COUNT(*) FILTER (WHERE has_file = TRUE) as with_files,
                COUNT(*) FILTER (WHERE status = 'wanted') as wanted,
                COUNT(*) FILTER (WHERE status = 'downloading') as downloading,
                COALESCE(SUM(file_size), 0) as total_size
            FROM movies
            """
        )
        return dict(stats)
