"""
Anime repository with episode handling and batch operations.
"""
from typing import List, Optional, Dict, Any
import asyncpg


class AnimeRepository:
    """Repository for anime database operations."""

    tableName = "anime"

    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn

    async def getById(self, animeId: int) -> Optional[Dict[str, Any]]:
        """Fetch an anime by ID."""
        row = await self.conn.fetchrow(
            "SELECT * FROM anime WHERE id = $1", animeId
        )
        return dict(row) if row else None

    async def listWithTags(
        self,
        limit: int = 100,
        offset: int = 0,
        monitoredOnly: bool = False,
    ) -> Dict[str, Any]:
        """Fetch anime with their tags in a single query using JSON aggregation."""
        whereClause = "WHERE a.monitored = TRUE" if monitoredOnly else ""

        query = f"""
            SELECT a.*,
                   COALESCE(
                       json_agg(
                           json_build_object('id', t.id, 'name', t.name, 'color', t.color)
                       ) FILTER (WHERE t.id IS NOT NULL),
                       '[]'::json
                   ) as tags
            FROM anime a
            LEFT JOIN media_tags mt ON a.id = mt.media_id AND mt.media_type = 'anime'
            LEFT JOIN tags t ON mt.tag_id = t.id
            {whereClause}
            GROUP BY a.id
            ORDER BY a.created_at DESC
            LIMIT $1 OFFSET $2
        """

        # Get total count of all anime in database
        total = await self.conn.fetchval("SELECT COUNT(*) FROM anime")

        rows = await self.conn.fetch(query, limit, offset)
        animeList = [dict(row) for row in rows]
        return {"anime": animeList, "total": total}

    async def getWithEpisodes(self, animeId: int) -> Optional[Dict[str, Any]]:
        """Fetch anime with all episodes."""
        anime = await self.getById(animeId)
        if not anime:
            return None

        episodeRows = await self.conn.fetch(
            """
            SELECT * FROM anime_episodes
            WHERE anime_id = $1
            ORDER BY episode_number
            """,
            animeId
        )

        anime["episodes"] = [dict(ep) for ep in episodeRows]
        return anime

    async def getByAnilistId(self, anilistId: int) -> Optional[Dict[str, Any]]:
        """Find anime by AniList ID."""
        row = await self.conn.fetchrow(
            "SELECT * FROM anime WHERE anilist_id = $1", anilistId
        )
        return dict(row) if row else None

    async def getByMalId(self, malId: int) -> Optional[Dict[str, Any]]:
        """Find anime by MyAnimeList ID."""
        row = await self.conn.fetchrow(
            "SELECT * FROM anime WHERE mal_id = $1", malId
        )
        return dict(row) if row else None

    async def existsByAnilistId(self, anilistId: int) -> bool:
        """Check if anime with the given AniList ID exists."""
        result = await self.conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM anime WHERE anilist_id = $1)", anilistId
        )
        return result

    async def getWanted(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get anime with wanted episodes for wanted search."""
        rows = await self.conn.fetch(
            """
            SELECT DISTINCT a.*, mp.name as profile_name
            FROM anime a
            LEFT JOIN media_profiles mp ON a.media_profile_id = mp.id
            JOIN anime_episodes e ON e.anime_id = a.id
            WHERE a.monitored = TRUE
              AND e.monitored = TRUE
              AND e.has_file = FALSE
            ORDER BY a.created_at DESC
            LIMIT $1
            """,
            limit
        )
        return [dict(row) for row in rows]

    async def getWantedEpisodes(self, animeId: int) -> List[Dict[str, Any]]:
        """Get wanted episodes for a specific anime."""
        rows = await self.conn.fetch(
            """
            SELECT e.*, a.title as anime_title, a.anilist_id
            FROM anime_episodes e
            JOIN anime a ON e.anime_id = a.id
            WHERE e.anime_id = $1
              AND e.monitored = TRUE
              AND e.has_file = FALSE
            ORDER BY e.episode_number
            """,
            animeId
        )
        return [dict(row) for row in rows]

    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new anime."""
        columns = ", ".join(data.keys())
        placeholders = ", ".join(f"${i+1}" for i in range(len(data)))
        row = await self.conn.fetchrow(
            f"INSERT INTO anime ({columns}) VALUES ({placeholders}) RETURNING *",
            *data.values()
        )
        return dict(row)

    async def update(self, animeId: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an anime."""
        if not data:
            return await self.getById(animeId)

        setClause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(data.keys()))
        row = await self.conn.fetchrow(
            f"UPDATE anime SET {setClause}, updated_at = NOW() WHERE id = $1 RETURNING *",
            animeId, *data.values()
        )
        return dict(row) if row else None

    async def updateBatch(self, ids: List[int], data: Dict[str, Any]) -> int:
        """Batch update multiple anime."""
        if not ids or not data:
            return 0

        setClause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(data.keys()))
        result = await self.conn.execute(
            f"UPDATE anime SET {setClause}, updated_at = NOW() WHERE id = ANY($1)",
            ids, *data.values()
        )
        return int(result.split()[-1])

    async def delete(self, animeId: int) -> bool:
        """Delete an anime (cascades to episodes)."""
        result = await self.conn.execute(
            "DELETE FROM anime WHERE id = $1", animeId
        )
        return result == "DELETE 1"

    async def deleteWithRelations(self, animeId: int) -> bool:
        """Delete anime and all related records."""
        await self.conn.execute(
            "DELETE FROM download_history WHERE media_type = 'anime' AND media_id = $1",
            animeId
        )
        await self.conn.execute(
            "DELETE FROM blocklist WHERE media_type = 'anime' AND media_id = $1",
            animeId
        )
        await self.conn.execute(
            "DELETE FROM media_tags WHERE media_type = 'anime' AND media_id = $1",
            animeId
        )
        return await self.delete(animeId)


class AnimeEpisodeRepository:
    """Repository for anime episode operations."""

    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn

    async def getById(self, episodeId: int) -> Optional[Dict[str, Any]]:
        """Get an episode by ID."""
        row = await self.conn.fetchrow(
            "SELECT * FROM anime_episodes WHERE id = $1", episodeId
        )
        return dict(row) if row else None

    async def getByAnimeAndNumber(
        self, animeId: int, episodeNumber: int
    ) -> Optional[Dict[str, Any]]:
        """Get an episode by anime and episode number."""
        row = await self.conn.fetchrow(
            "SELECT * FROM anime_episodes WHERE anime_id = $1 AND episode_number = $2",
            animeId, episodeNumber
        )
        return dict(row) if row else None

    async def getByAnimeId(self, animeId: int) -> List[Dict[str, Any]]:
        """Get all episodes for an anime."""
        rows = await self.conn.fetch(
            "SELECT * FROM anime_episodes WHERE anime_id = $1 ORDER BY episode_number",
            animeId
        )
        return [dict(row) for row in rows]

    async def upsert(
        self, animeId: int, episodeNumber: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Insert or update an episode."""
        data["anime_id"] = animeId
        data["episode_number"] = episodeNumber

        columns = ", ".join(data.keys())
        placeholders = ", ".join(f"${i+1}" for i in range(len(data)))
        updateCols = ", ".join(
            f"{k} = EXCLUDED.{k}" for k in data.keys()
            if k not in ("anime_id", "episode_number")
        )

        row = await self.conn.fetchrow(
            f"""
            INSERT INTO anime_episodes ({columns})
            VALUES ({placeholders})
            ON CONFLICT (anime_id, episode_number)
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
            UPDATE anime_episodes SET
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
            "UPDATE anime_episodes SET monitored = $2, updated_at = NOW() WHERE id = ANY($1)",
            ids, monitored
        )
        return int(result.split()[-1])
