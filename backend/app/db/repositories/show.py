"""
Show repository with season/episode handling and batch operations.
"""
from typing import List, Optional, Dict, Any
import asyncpg

from app.db.repositories.base import BaseRepository


class ShowRepository:
    """Repository for TV show database operations."""

    tableName = "shows"

    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn

    async def getById(self, showId: int) -> Optional[Dict[str, Any]]:
        """Fetch a show by ID."""
        row = await self.conn.fetchrow(
            "SELECT * FROM shows WHERE id = $1", showId
        )
        return dict(row) if row else None

    async def listWithTags(
        self,
        limit: int = 100,
        offset: int = 0,
        monitoredOnly: bool = False,
    ) -> Dict[str, Any]:
        """Fetch shows with their tags in a single query using JSON aggregation."""
        whereClause = "WHERE s.monitored = TRUE" if monitoredOnly else ""

        query = f"""
            SELECT s.*,
                   COALESCE(
                       json_agg(
                           json_build_object('id', t.id, 'name', t.name, 'color', t.color)
                       ) FILTER (WHERE t.id IS NOT NULL),
                       '[]'::json
                   ) as tags
            FROM shows s
            LEFT JOIN media_tags mt ON s.id = mt.media_id AND mt.media_type = 'show'
            LEFT JOIN tags t ON mt.tag_id = t.id
            {whereClause}
            GROUP BY s.id
            ORDER BY s.created_at DESC
            LIMIT $1 OFFSET $2
        """

        # Get total count of all shows in database
        total = await self.conn.fetchval("SELECT COUNT(*) FROM shows")

        rows = await self.conn.fetch(query, limit, offset)
        shows = [dict(row) for row in rows]
        return {"shows": shows, "total": total}

    async def getWithSeasonsAndEpisodes(self, showId: int) -> Optional[Dict[str, Any]]:
        """Fetch a show with all seasons and episodes."""
        show = await self.getById(showId)
        if not show:
            return None

        # Fetch seasons
        seasonRows = await self.conn.fetch(
            """
            SELECT * FROM seasons
            WHERE show_id = $1
            ORDER BY season_number
            """,
            showId
        )

        # Fetch all episodes for this show
        episodeRows = await self.conn.fetch(
            """
            SELECT * FROM episodes
            WHERE show_id = $1
            ORDER BY season_number, episode_number
            """,
            showId
        )

        # Group episodes by season
        episodesBySeason = {}
        for ep in episodeRows:
            seasonNum = ep["season_number"]
            if seasonNum not in episodesBySeason:
                episodesBySeason[seasonNum] = []
            episodesBySeason[seasonNum].append(dict(ep))

        seasons = []
        for season in seasonRows:
            seasonDict = dict(season)
            seasonDict["episodes"] = episodesBySeason.get(season["season_number"], [])
            seasons.append(seasonDict)

        show["seasons"] = seasons
        return show

    async def getByTmdbId(self, tmdbId: int) -> Optional[Dict[str, Any]]:
        """Find a show by TMDB ID."""
        row = await self.conn.fetchrow(
            "SELECT * FROM shows WHERE tmdb_id = $1", tmdbId
        )
        return dict(row) if row else None

    async def existsByTmdbId(self, tmdbId: int) -> bool:
        """Check if a show with the given TMDB ID exists."""
        result = await self.conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM shows WHERE tmdb_id = $1)", tmdbId
        )
        return result

    async def getWanted(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get shows with wanted episodes for wanted search."""
        rows = await self.conn.fetch(
            """
            SELECT DISTINCT s.*, mp.name as profile_name
            FROM shows s
            LEFT JOIN media_profiles mp ON s.media_profile_id = mp.id
            JOIN episodes e ON e.show_id = s.id
            WHERE s.monitored = TRUE
              AND e.monitored = TRUE
              AND e.has_file = FALSE
            ORDER BY s.created_at DESC
            LIMIT $1
            """,
            limit
        )
        return [dict(row) for row in rows]

    async def getWantedEpisodes(self, showId: int) -> List[Dict[str, Any]]:
        """Get wanted episodes for a specific show."""
        rows = await self.conn.fetch(
            """
            SELECT e.*, s.title as show_title, s.tmdb_id as show_tmdb_id
            FROM episodes e
            JOIN shows s ON e.show_id = s.id
            WHERE e.show_id = $1
              AND e.monitored = TRUE
              AND e.has_file = FALSE
            ORDER BY e.season_number, e.episode_number
            """,
            showId
        )
        return [dict(row) for row in rows]

    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new show."""
        columns = ", ".join(data.keys())
        placeholders = ", ".join(f"${i+1}" for i in range(len(data)))
        row = await self.conn.fetchrow(
            f"INSERT INTO shows ({columns}) VALUES ({placeholders}) RETURNING *",
            *data.values()
        )
        return dict(row)

    async def update(self, showId: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a show."""
        if not data:
            return await self.getById(showId)

        setClause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(data.keys()))
        row = await self.conn.fetchrow(
            f"UPDATE shows SET {setClause}, updated_at = NOW() WHERE id = $1 RETURNING *",
            showId, *data.values()
        )
        return dict(row) if row else None

    async def updateBatch(self, ids: List[int], data: Dict[str, Any]) -> int:
        """Batch update multiple shows."""
        if not ids or not data:
            return 0

        setClause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(data.keys()))
        result = await self.conn.execute(
            f"UPDATE shows SET {setClause}, updated_at = NOW() WHERE id = ANY($1)",
            ids, *data.values()
        )
        return int(result.split()[-1])

    async def delete(self, showId: int) -> bool:
        """Delete a show (cascades to seasons and episodes)."""
        result = await self.conn.execute(
            "DELETE FROM shows WHERE id = $1", showId
        )
        return result == "DELETE 1"

    async def deleteWithRelations(self, showId: int) -> bool:
        """Delete a show and all related records."""
        await self.conn.execute(
            "DELETE FROM download_history WHERE media_type = 'show' AND media_id = $1",
            showId
        )
        await self.conn.execute(
            "DELETE FROM blocklist WHERE media_type = 'show' AND media_id = $1",
            showId
        )
        await self.conn.execute(
            "DELETE FROM media_tags WHERE media_type = 'show' AND media_id = $1",
            showId
        )
        return await self.delete(showId)


class SeasonRepository:
    """Repository for TV season operations."""

    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn

    async def getByShowAndNumber(self, showId: int, seasonNumber: int) -> Optional[Dict[str, Any]]:
        """Get a season by show ID and season number."""
        row = await self.conn.fetchrow(
            "SELECT * FROM seasons WHERE show_id = $1 AND season_number = $2",
            showId, seasonNumber
        )
        return dict(row) if row else None

    async def getByShowId(self, showId: int) -> List[Dict[str, Any]]:
        """Get all seasons for a show."""
        rows = await self.conn.fetch(
            "SELECT * FROM seasons WHERE show_id = $1 ORDER BY season_number",
            showId
        )
        return [dict(row) for row in rows]

    async def upsert(self, showId: int, seasonNumber: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert or update a season."""
        data["show_id"] = showId
        data["season_number"] = seasonNumber

        columns = ", ".join(data.keys())
        placeholders = ", ".join(f"${i+1}" for i in range(len(data)))
        updateCols = ", ".join(f"{k} = EXCLUDED.{k}" for k in data.keys() if k not in ("show_id", "season_number"))

        row = await self.conn.fetchrow(
            f"""
            INSERT INTO seasons ({columns})
            VALUES ({placeholders})
            ON CONFLICT (show_id, season_number)
            DO UPDATE SET {updateCols}, updated_at = NOW()
            RETURNING *
            """,
            *data.values()
        )
        return dict(row)

    async def updateMonitoredBatch(self, ids: List[int], monitored: bool) -> int:
        """Batch update monitored flag for multiple seasons."""
        if not ids:
            return 0
        result = await self.conn.execute(
            "UPDATE seasons SET monitored = $2, updated_at = NOW() WHERE id = ANY($1)",
            ids, monitored
        )
        return int(result.split()[-1])


class EpisodeRepository:
    """Repository for TV episode operations."""

    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn

    async def getById(self, episodeId: int) -> Optional[Dict[str, Any]]:
        """Get an episode by ID."""
        row = await self.conn.fetchrow(
            "SELECT * FROM episodes WHERE id = $1", episodeId
        )
        return dict(row) if row else None

    async def getByShowSeasonEpisode(
        self, showId: int, seasonNumber: int, episodeNumber: int
    ) -> Optional[Dict[str, Any]]:
        """Get an episode by show, season, and episode number."""
        row = await self.conn.fetchrow(
            """
            SELECT * FROM episodes
            WHERE show_id = $1 AND season_number = $2 AND episode_number = $3
            """,
            showId, seasonNumber, episodeNumber
        )
        return dict(row) if row else None

    async def getByShowId(self, showId: int) -> List[Dict[str, Any]]:
        """Get all episodes for a show."""
        rows = await self.conn.fetch(
            """
            SELECT * FROM episodes
            WHERE show_id = $1
            ORDER BY season_number, episode_number
            """,
            showId
        )
        return [dict(row) for row in rows]

    async def getBySeasonId(self, seasonId: int) -> List[Dict[str, Any]]:
        """Get all episodes for a season."""
        rows = await self.conn.fetch(
            """
            SELECT * FROM episodes
            WHERE season_id = $1
            ORDER BY episode_number
            """,
            seasonId
        )
        return [dict(row) for row in rows]

    async def upsert(
        self, showId: int, seasonNumber: int, episodeNumber: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Insert or update an episode."""
        data["show_id"] = showId
        data["season_number"] = seasonNumber
        data["episode_number"] = episodeNumber

        columns = ", ".join(data.keys())
        placeholders = ", ".join(f"${i+1}" for i in range(len(data)))
        updateCols = ", ".join(
            f"{k} = EXCLUDED.{k}" for k in data.keys()
            if k not in ("show_id", "season_number", "episode_number")
        )

        row = await self.conn.fetchrow(
            f"""
            INSERT INTO episodes ({columns})
            VALUES ({placeholders})
            ON CONFLICT (show_id, season_number, episode_number)
            DO UPDATE SET {updateCols}, updated_at = NOW()
            RETURNING *
            """,
            *data.values()
        )
        return dict(row)

    async def updateFileInfo(
        self,
        episodeId: int,
        hasFile: bool,
        filePath: Optional[str] = None,
        fileSize: Optional[int] = None,
        qualityDetected: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update file-related fields for an episode."""
        row = await self.conn.fetchrow(
            """
            UPDATE episodes SET
                has_file = $2, file_path = $3, file_size = $4,
                quality_detected = $5, updated_at = NOW()
            WHERE id = $1
            RETURNING *
            """,
            episodeId, hasFile, filePath, fileSize, qualityDetected
        )
        return dict(row) if row else None

    async def updateMonitoredBatch(self, ids: List[int], monitored: bool) -> int:
        """Batch update monitored flag for multiple episodes."""
        if not ids:
            return 0
        result = await self.conn.execute(
            "UPDATE episodes SET monitored = $2, updated_at = NOW() WHERE id = ANY($1)",
            ids, monitored
        )
        return int(result.split()[-1])
