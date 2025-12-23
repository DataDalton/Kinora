"""
Download history repository with batch progress updates.
"""
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
import asyncpg


class DownloadHistoryRepository:
    """Repository for download history operations."""

    tableName = "download_history"

    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn

    async def getById(self, id: int) -> Optional[Dict[str, Any]]:
        """Get a download record by ID."""
        row = await self.conn.fetchrow(
            "SELECT * FROM download_history WHERE id = $1", id
        )
        return dict(row) if row else None

    async def getByHash(self, torrentHash: str) -> Optional[Dict[str, Any]]:
        """Get a download record by torrent hash."""
        row = await self.conn.fetchrow(
            "SELECT * FROM download_history WHERE torrent_hash = $1", torrentHash
        )
        return dict(row) if row else None

    async def getByMediaId(
        self, mediaId: int, mediaType: str
    ) -> List[Dict[str, Any]]:
        """Get download history for a specific media item."""
        rows = await self.conn.fetch(
            """
            SELECT * FROM download_history
            WHERE media_id = $1 AND media_type = $2
            ORDER BY created_at DESC
            """,
            mediaId, mediaType
        )
        return [dict(row) for row in rows]

    async def getActive(self) -> List[Dict[str, Any]]:
        """Get all active (non-completed, non-failed) downloads."""
        rows = await self.conn.fetch(
            """
            SELECT * FROM download_history
            WHERE status NOT IN ('completed', 'failed', 'removed')
            ORDER BY created_at DESC
            """
        )
        return [dict(row) for row in rows]

    async def getByStatus(self, status: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get downloads by status."""
        rows = await self.conn.fetch(
            """
            SELECT * FROM download_history
            WHERE status = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            status, limit
        )
        return [dict(row) for row in rows]

    async def list(
        self,
        limit: int = 100,
        offset: int = 0,
        mediaType: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List download history with optional filters."""
        conditions = []
        params = []
        paramIdx = 1

        if mediaType:
            conditions.append(f"media_type = ${paramIdx}")
            params.append(mediaType)
            paramIdx += 1

        if status:
            conditions.append(f"status = ${paramIdx}")
            params.append(status)
            paramIdx += 1

        whereClause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        countQuery = f"SELECT COUNT(*) FROM download_history {whereClause}"
        total = await self.conn.fetchval(countQuery, *params)

        params.extend([limit, offset])
        query = f"""
            SELECT * FROM download_history
            {whereClause}
            ORDER BY created_at DESC
            LIMIT ${paramIdx} OFFSET ${paramIdx + 1}
        """

        rows = await self.conn.fetch(query, *params)
        return {"history": [dict(row) for row in rows], "total": total}

    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new download record."""
        columns = ", ".join(data.keys())
        placeholders = ", ".join(f"${i+1}" for i in range(len(data)))
        row = await self.conn.fetchrow(
            f"INSERT INTO download_history ({columns}) VALUES ({placeholders}) RETURNING *",
            *data.values()
        )
        return dict(row)

    async def updateProgress(
        self, torrentHash: str, progress: float, status: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Update progress for a download."""
        if status:
            row = await self.conn.fetchrow(
                """
                UPDATE download_history
                SET progress = $2, status = $3, updated_at = NOW()
                WHERE torrent_hash = $1
                RETURNING *
                """,
                torrentHash, progress, status
            )
        else:
            row = await self.conn.fetchrow(
                """
                UPDATE download_history
                SET progress = $2, updated_at = NOW()
                WHERE torrent_hash = $1
                RETURNING *
                """,
                torrentHash, progress
            )
        return dict(row) if row else None

    async def updateProgressBatch(
        self, updates: List[Tuple[str, float, Optional[str]]]
    ) -> int:
        """Batch update progress for multiple downloads.

        Args:
            updates: List of (torrent_hash, progress, status) tuples.
                     status can be None to only update progress.
        """
        if not updates:
            return 0

        # Separate updates with and without status changes
        progressOnly = [(h, p) for h, p, s in updates if s is None]
        withStatus = [(h, p, s) for h, p, s in updates if s is not None]

        count = 0

        if progressOnly:
            # Use unnest for bulk update
            hashes = [h for h, _ in progressOnly]
            progresses = [p for _, p in progressOnly]

            result = await self.conn.execute(
                """
                UPDATE download_history dh
                SET progress = u.progress, updated_at = NOW()
                FROM (SELECT unnest($1::text[]) as hash, unnest($2::float[]) as progress) u
                WHERE dh.torrent_hash = u.hash
                """,
                hashes, progresses
            )
            count += int(result.split()[-1])

        if withStatus:
            hashes = [h for h, _, _ in withStatus]
            progresses = [p for _, p, _ in withStatus]
            statuses = [s for _, _, s in withStatus]

            result = await self.conn.execute(
                """
                UPDATE download_history dh
                SET progress = u.progress, status = u.status, updated_at = NOW()
                FROM (
                    SELECT unnest($1::text[]) as hash,
                           unnest($2::float[]) as progress,
                           unnest($3::text[]) as status
                ) u
                WHERE dh.torrent_hash = u.hash
                """,
                hashes, progresses, statuses
            )
            count += int(result.split()[-1])

        return count

    async def markCompleted(
        self, torrentHash: str, savePath: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Mark a download as completed."""
        row = await self.conn.fetchrow(
            """
            UPDATE download_history
            SET status = 'completed', progress = 100.0, completed_at = NOW(),
                save_path = COALESCE($2, save_path), updated_at = NOW()
            WHERE torrent_hash = $1
            RETURNING *
            """,
            torrentHash, savePath
        )
        return dict(row) if row else None

    async def markFailed(
        self, torrentHash: str, errorMessage: str
    ) -> Optional[Dict[str, Any]]:
        """Mark a download as failed."""
        row = await self.conn.fetchrow(
            """
            UPDATE download_history
            SET status = 'failed', error_message = $2, updated_at = NOW()
            WHERE torrent_hash = $1
            RETURNING *
            """,
            torrentHash, errorMessage
        )
        return dict(row) if row else None

    async def delete(self, id: int) -> bool:
        """Delete a download record."""
        result = await self.conn.execute(
            "DELETE FROM download_history WHERE id = $1", id
        )
        return result == "DELETE 1"

    async def deleteByHash(self, torrentHash: str) -> bool:
        """Delete a download record by hash."""
        result = await self.conn.execute(
            "DELETE FROM download_history WHERE torrent_hash = $1", torrentHash
        )
        return result == "DELETE 1"

    async def deleteByMedia(self, mediaId: int, mediaType: str) -> int:
        """Delete all download records for a media item."""
        result = await self.conn.execute(
            "DELETE FROM download_history WHERE media_id = $1 AND media_type = $2",
            mediaId, mediaType
        )
        return int(result.split()[-1])

    async def getStats(self) -> Dict[str, Any]:
        """Get download statistics."""
        stats = await self.conn.fetchrow(
            """
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE status = 'downloading') as downloading,
                COUNT(*) FILTER (WHERE status = 'completed') as completed,
                COUNT(*) FILTER (WHERE status = 'failed') as failed,
                COUNT(*) FILTER (WHERE status = 'pending') as pending,
                COALESCE(SUM(size) FILTER (WHERE status = 'completed'), 0) as total_downloaded_size
            FROM download_history
            """
        )
        return dict(stats)
