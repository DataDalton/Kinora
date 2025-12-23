"""
Media profile repository.
"""
from typing import List, Optional, Dict, Any
import asyncpg


class MediaProfileRepository:
    """Repository for media profile operations."""

    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn

    async def getById(self, profileId: int) -> Optional[Dict[str, Any]]:
        """Get a profile by ID."""
        row = await self.conn.fetchrow(
            "SELECT * FROM media_profiles WHERE id = $1", profileId
        )
        return dict(row) if row else None

    async def getByName(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a profile by name."""
        row = await self.conn.fetchrow(
            "SELECT * FROM media_profiles WHERE name = $1", name
        )
        return dict(row) if row else None

    async def getByIds(self, ids: List[int]) -> List[Dict[str, Any]]:
        """Batch fetch multiple profiles by IDs."""
        if not ids:
            return []
        rows = await self.conn.fetch(
            "SELECT * FROM media_profiles WHERE id = ANY($1)", ids
        )
        return [dict(row) for row in rows]

    async def list(self) -> List[Dict[str, Any]]:
        """Get all profiles."""
        rows = await self.conn.fetch(
            "SELECT * FROM media_profiles ORDER BY name"
        )
        return [dict(row) for row in rows]

    async def listWithUsageCounts(self) -> List[Dict[str, Any]]:
        """Get all profiles with usage counts by media type."""
        rows = await self.conn.fetch(
            """
            SELECT mp.*,
                   COUNT(DISTINCT m.id) as movie_count,
                   COUNT(DISTINCT s.id) as show_count,
                   COUNT(DISTINCT a.id) as anime_count,
                   COUNT(DISTINCT al.id) as album_count
            FROM media_profiles mp
            LEFT JOIN movies m ON mp.id = m.media_profile_id
            LEFT JOIN shows s ON mp.id = s.media_profile_id
            LEFT JOIN anime a ON mp.id = a.media_profile_id
            LEFT JOIN albums al ON mp.id = al.media_profile_id
            GROUP BY mp.id
            ORDER BY mp.name
            """
        )
        return [dict(row) for row in rows]

    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new profile."""
        columns = ", ".join(data.keys())
        placeholders = ", ".join(f"${i+1}" for i in range(len(data)))
        row = await self.conn.fetchrow(
            f"INSERT INTO media_profiles ({columns}) VALUES ({placeholders}) RETURNING *",
            *data.values()
        )
        return dict(row)

    async def update(self, profileId: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a profile."""
        if not data:
            return await self.getById(profileId)

        setClause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(data.keys()))
        row = await self.conn.fetchrow(
            f"UPDATE media_profiles SET {setClause}, updated_at = NOW() WHERE id = $1 RETURNING *",
            profileId, *data.values()
        )
        return dict(row) if row else None

    async def delete(self, profileId: int) -> bool:
        """Delete a profile."""
        result = await self.conn.execute(
            "DELETE FROM media_profiles WHERE id = $1", profileId
        )
        return result == "DELETE 1"

    async def exists(self, profileId: int) -> bool:
        """Check if a profile exists."""
        result = await self.conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM media_profiles WHERE id = $1)", profileId
        )
        return result

    async def nameExists(self, name: str, excludeId: Optional[int] = None) -> bool:
        """Check if a profile name already exists."""
        if excludeId:
            result = await self.conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM media_profiles WHERE name = $1 AND id != $2)",
                name, excludeId
            )
        else:
            result = await self.conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM media_profiles WHERE name = $1)", name
            )
        return result
