"""
Tag repository for managing media tags.
"""
from typing import List, Optional, Dict, Any
import asyncpg


class TagRepository:
    """Repository for tag operations."""

    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn

    async def getById(self, tagId: int) -> Optional[Dict[str, Any]]:
        """Get a tag by ID."""
        row = await self.conn.fetchrow(
            "SELECT * FROM tags WHERE id = $1", tagId
        )
        return dict(row) if row else None

    async def getByName(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a tag by name."""
        row = await self.conn.fetchrow(
            "SELECT * FROM tags WHERE name = $1", name
        )
        return dict(row) if row else None

    async def list(self) -> List[Dict[str, Any]]:
        """Get all tags."""
        rows = await self.conn.fetch(
            "SELECT * FROM tags ORDER BY name"
        )
        return [dict(row) for row in rows]

    async def listWithCounts(self) -> List[Dict[str, Any]]:
        """Get all tags with usage counts."""
        rows = await self.conn.fetch(
            """
            SELECT t.*, COUNT(mt.id) as usage_count
            FROM tags t
            LEFT JOIN media_tags mt ON t.id = mt.tag_id
            GROUP BY t.id
            ORDER BY t.name
            """
        )
        return [dict(row) for row in rows]

    async def create(self, name: str, color: str = "#6366f1") -> Dict[str, Any]:
        """Create a new tag."""
        row = await self.conn.fetchrow(
            "INSERT INTO tags (name, color) VALUES ($1, $2) RETURNING *",
            name, color
        )
        return dict(row)

    async def update(self, tagId: int, name: Optional[str] = None, color: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Update a tag."""
        updates = []
        params = []
        paramIdx = 1

        if name is not None:
            updates.append(f"name = ${paramIdx}")
            params.append(name)
            paramIdx += 1

        if color is not None:
            updates.append(f"color = ${paramIdx}")
            params.append(color)
            paramIdx += 1

        if not updates:
            return await self.getById(tagId)

        params.append(tagId)
        row = await self.conn.fetchrow(
            f"UPDATE tags SET {', '.join(updates)} WHERE id = ${paramIdx} RETURNING *",
            *params
        )
        return dict(row) if row else None

    async def delete(self, tagId: int) -> bool:
        """Delete a tag (cascades to media_tags)."""
        result = await self.conn.execute(
            "DELETE FROM tags WHERE id = $1", tagId
        )
        return result == "DELETE 1"


class MediaTagRepository:
    """Repository for media-tag associations."""

    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn

    async def getTagsForMedia(self, mediaType: str, mediaId: int) -> List[Dict[str, Any]]:
        """Get all tags for a specific media item."""
        rows = await self.conn.fetch(
            """
            SELECT t.id, t.name, t.color
            FROM tags t
            JOIN media_tags mt ON t.id = mt.tag_id
            WHERE mt.media_type = $1 AND mt.media_id = $2
            ORDER BY t.name
            """,
            mediaType, mediaId
        )
        return [dict(row) for row in rows]

    async def getMediaForTag(self, tagId: int, mediaType: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all media items with a specific tag."""
        if mediaType:
            rows = await self.conn.fetch(
                """
                SELECT media_type, media_id
                FROM media_tags
                WHERE tag_id = $1 AND media_type = $2
                """,
                tagId, mediaType
            )
        else:
            rows = await self.conn.fetch(
                "SELECT media_type, media_id FROM media_tags WHERE tag_id = $1",
                tagId
            )
        return [dict(row) for row in rows]

    async def addTag(self, mediaType: str, mediaId: int, tagId: int) -> bool:
        """Add a tag to a media item."""
        try:
            await self.conn.execute(
                """
                INSERT INTO media_tags (media_type, media_id, tag_id)
                VALUES ($1, $2, $3)
                ON CONFLICT (tag_id, media_type, media_id) DO NOTHING
                """,
                mediaType, mediaId, tagId
            )
            return True
        except Exception:
            return False

    async def addTagsBatch(self, mediaType: str, mediaIds: List[int], tagId: int) -> int:
        """Add a tag to multiple media items."""
        if not mediaIds:
            return 0

        # Use unnest for efficient batch insert
        result = await self.conn.execute(
            """
            INSERT INTO media_tags (media_type, media_id, tag_id)
            SELECT $1, unnest($2::int[]), $3
            ON CONFLICT (tag_id, media_type, media_id) DO NOTHING
            """,
            mediaType, mediaIds, tagId
        )
        return int(result.split()[-1])

    async def removeTag(self, mediaType: str, mediaId: int, tagId: int) -> bool:
        """Remove a tag from a media item."""
        result = await self.conn.execute(
            """
            DELETE FROM media_tags
            WHERE media_type = $1 AND media_id = $2 AND tag_id = $3
            """,
            mediaType, mediaId, tagId
        )
        return result == "DELETE 1"

    async def removeTagsBatch(self, mediaType: str, mediaIds: List[int], tagId: int) -> int:
        """Remove a tag from multiple media items."""
        if not mediaIds:
            return 0

        result = await self.conn.execute(
            """
            DELETE FROM media_tags
            WHERE media_type = $1 AND media_id = ANY($2) AND tag_id = $3
            """,
            mediaType, mediaIds, tagId
        )
        return int(result.split()[-1])

    async def setTags(self, mediaType: str, mediaId: int, tagIds: List[int]) -> None:
        """Set all tags for a media item (replaces existing)."""
        # Delete existing
        await self.conn.execute(
            "DELETE FROM media_tags WHERE media_type = $1 AND media_id = $2",
            mediaType, mediaId
        )

        # Add new
        if tagIds:
            await self.conn.execute(
                """
                INSERT INTO media_tags (media_type, media_id, tag_id)
                SELECT $1, $2, unnest($3::int[])
                """,
                mediaType, mediaId, tagIds
            )

    async def removeAllFromMedia(self, mediaType: str, mediaId: int) -> int:
        """Remove all tags from a media item."""
        result = await self.conn.execute(
            "DELETE FROM media_tags WHERE media_type = $1 AND media_id = $2",
            mediaType, mediaId
        )
        return int(result.split()[-1])
