"""
Music repositories for artists, albums, and tracks.
"""
from typing import List, Optional, Dict, Any
import asyncpg


class ArtistRepository:
    """Repository for artist operations."""

    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn

    async def getById(self, artistId: int) -> Optional[Dict[str, Any]]:
        """Get an artist by ID."""
        row = await self.conn.fetchrow(
            "SELECT * FROM artists WHERE id = $1", artistId
        )
        return dict(row) if row else None

    async def getByDeezerId(self, deezerId: int) -> Optional[Dict[str, Any]]:
        """Get an artist by Deezer ID."""
        row = await self.conn.fetchrow(
            "SELECT * FROM artists WHERE deezer_id = $1", deezerId
        )
        return dict(row) if row else None

    async def list(
        self, limit: int = 100, offset: int = 0, monitoredOnly: bool = False
    ) -> Dict[str, Any]:
        """List artists with optional monitoring filter."""
        whereClause = "WHERE monitored = TRUE" if monitoredOnly else ""
        rows = await self.conn.fetch(
            f"""
            SELECT * FROM artists
            {whereClause}
            ORDER BY name
            LIMIT $1 OFFSET $2
            """,
            limit, offset
        )
        return {"artists": [dict(row) for row in rows], "total": len(rows)}

    async def getWithAlbums(self, artistId: int) -> Optional[Dict[str, Any]]:
        """Get an artist with all their albums."""
        artist = await self.getById(artistId)
        if not artist:
            return None

        albumRows = await self.conn.fetch(
            """
            SELECT * FROM albums
            WHERE artist_id = $1
            ORDER BY release_date DESC
            """,
            artistId
        )
        artist["albums"] = [dict(album) for album in albumRows]
        return artist

    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new artist."""
        columns = ", ".join(data.keys())
        placeholders = ", ".join(f"${i+1}" for i in range(len(data)))
        row = await self.conn.fetchrow(
            f"INSERT INTO artists ({columns}) VALUES ({placeholders}) RETURNING *",
            *data.values()
        )
        return dict(row)

    async def update(self, artistId: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an artist."""
        if not data:
            return await self.getById(artistId)

        setClause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(data.keys()))
        row = await self.conn.fetchrow(
            f"UPDATE artists SET {setClause}, updated_at = NOW() WHERE id = $1 RETURNING *",
            artistId, *data.values()
        )
        return dict(row) if row else None

    async def delete(self, artistId: int) -> bool:
        """Delete an artist (cascades to albums and tracks)."""
        result = await self.conn.execute(
            "DELETE FROM artists WHERE id = $1", artistId
        )
        return result == "DELETE 1"


class AlbumRepository:
    """Repository for album operations."""

    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn

    async def getById(self, albumId: int) -> Optional[Dict[str, Any]]:
        """Get an album by ID."""
        row = await self.conn.fetchrow(
            "SELECT * FROM albums WHERE id = $1", albumId
        )
        return dict(row) if row else None

    async def getByDeezerId(self, deezerId: int) -> Optional[Dict[str, Any]]:
        """Get an album by Deezer ID."""
        row = await self.conn.fetchrow(
            "SELECT * FROM albums WHERE deezer_id = $1", deezerId
        )
        return dict(row) if row else None

    async def listWithTags(
        self, limit: int = 100, offset: int = 0, monitoredOnly: bool = False
    ) -> Dict[str, Any]:
        """List albums with tags."""
        whereClause = "WHERE al.monitored = TRUE" if monitoredOnly else ""

        query = f"""
            SELECT al.*,
                   ar.name as artist_name,
                   COALESCE(
                       json_agg(
                           json_build_object('id', t.id, 'name', t.name, 'color', t.color)
                       ) FILTER (WHERE t.id IS NOT NULL),
                       '[]'::json
                   ) as tags
            FROM albums al
            LEFT JOIN artists ar ON al.artist_id = ar.id
            LEFT JOIN media_tags mt ON al.id = mt.media_id AND mt.media_type = 'album'
            LEFT JOIN tags t ON mt.tag_id = t.id
            {whereClause}
            GROUP BY al.id, ar.name
            ORDER BY al.created_at DESC
            LIMIT $1 OFFSET $2
        """

        rows = await self.conn.fetch(query, limit, offset)
        return {"albums": [dict(row) for row in rows], "total": len(rows)}

    async def getWithTracks(self, albumId: int) -> Optional[Dict[str, Any]]:
        """Get an album with all tracks."""
        album = await self.getById(albumId)
        if not album:
            return None

        trackRows = await self.conn.fetch(
            """
            SELECT * FROM tracks
            WHERE album_id = $1
            ORDER BY disk_number, track_position
            """,
            albumId
        )
        album["tracks"] = [dict(track) for track in trackRows]
        return album

    async def getWanted(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get albums with status 'wanted' for wanted search."""
        rows = await self.conn.fetch(
            """
            SELECT al.*, ar.name as artist_name, mp.name as profile_name
            FROM albums al
            LEFT JOIN artists ar ON al.artist_id = ar.id
            LEFT JOIN media_profiles mp ON al.media_profile_id = mp.id
            WHERE al.status = 'wanted' AND al.monitored = TRUE
            ORDER BY al.created_at DESC
            LIMIT $1
            """,
            limit
        )
        return [dict(row) for row in rows]

    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new album."""
        columns = ", ".join(data.keys())
        placeholders = ", ".join(f"${i+1}" for i in range(len(data)))
        row = await self.conn.fetchrow(
            f"INSERT INTO albums ({columns}) VALUES ({placeholders}) RETURNING *",
            *data.values()
        )
        return dict(row)

    async def update(self, albumId: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an album."""
        if not data:
            return await self.getById(albumId)

        setClause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(data.keys()))
        row = await self.conn.fetchrow(
            f"UPDATE albums SET {setClause}, updated_at = NOW() WHERE id = $1 RETURNING *",
            albumId, *data.values()
        )
        return dict(row) if row else None

    async def updateBatch(self, ids: List[int], data: Dict[str, Any]) -> int:
        """Batch update multiple albums."""
        if not ids or not data:
            return 0

        setClause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(data.keys()))
        result = await self.conn.execute(
            f"UPDATE albums SET {setClause}, updated_at = NOW() WHERE id = ANY($1)",
            ids, *data.values()
        )
        return int(result.split()[-1])

    async def delete(self, albumId: int) -> bool:
        """Delete an album (cascades to tracks)."""
        result = await self.conn.execute(
            "DELETE FROM albums WHERE id = $1", albumId
        )
        return result == "DELETE 1"


class TrackRepository:
    """Repository for track operations."""

    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn

    async def getById(self, trackId: int) -> Optional[Dict[str, Any]]:
        """Get a track by ID."""
        row = await self.conn.fetchrow(
            "SELECT * FROM tracks WHERE id = $1", trackId
        )
        return dict(row) if row else None

    async def getByDeezerId(self, deezerId: int) -> Optional[Dict[str, Any]]:
        """Get a track by Deezer ID."""
        row = await self.conn.fetchrow(
            "SELECT * FROM tracks WHERE deezer_id = $1", deezerId
        )
        return dict(row) if row else None

    async def getByAlbumId(self, albumId: int) -> List[Dict[str, Any]]:
        """Get all tracks for an album."""
        rows = await self.conn.fetch(
            """
            SELECT * FROM tracks
            WHERE album_id = $1
            ORDER BY disk_number, track_position
            """,
            albumId
        )
        return [dict(row) for row in rows]

    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new track."""
        columns = ", ".join(data.keys())
        placeholders = ", ".join(f"${i+1}" for i in range(len(data)))
        row = await self.conn.fetchrow(
            f"INSERT INTO tracks ({columns}) VALUES ({placeholders}) RETURNING *",
            *data.values()
        )
        return dict(row)

    async def createMany(self, tracks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Batch create multiple tracks."""
        if not tracks:
            return []

        columns = list(tracks[0].keys())
        columnStr = ", ".join(columns)

        valuesClauses = []
        allValues = []
        paramIdx = 1
        for track in tracks:
            placeholders = ", ".join(f"${paramIdx + i}" for i in range(len(columns)))
            valuesClauses.append(f"({placeholders})")
            allValues.extend(track[col] for col in columns)
            paramIdx += len(columns)

        query = f"INSERT INTO tracks ({columnStr}) VALUES {', '.join(valuesClauses)} RETURNING *"
        rows = await self.conn.fetch(query, *allValues)
        return [dict(row) for row in rows]

    async def updateFileInfo(
        self,
        trackId: int,
        hasFile: bool,
        filePath: Optional[str] = None,
        fileSize: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update file-related fields for a track."""
        row = await self.conn.fetchrow(
            """
            UPDATE tracks SET
                has_file = $2, file_path = $3, file_size = $4, updated_at = NOW()
            WHERE id = $1
            RETURNING *
            """,
            trackId, hasFile, filePath, fileSize
        )
        return dict(row) if row else None

    async def update(self, trackId: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a track."""
        if not data:
            return await self.getById(trackId)

        setClause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(data.keys()))
        row = await self.conn.fetchrow(
            f"UPDATE tracks SET {setClause}, updated_at = NOW() WHERE id = $1 RETURNING *",
            trackId, *data.values()
        )
        return dict(row) if row else None

    async def delete(self, trackId: int) -> bool:
        """Delete a track."""
        result = await self.conn.execute(
            "DELETE FROM tracks WHERE id = $1", trackId
        )
        return result == "DELETE 1"
