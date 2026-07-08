"""
Transfer statistics history.

Records a periodic sample of the download client's global transfer stats into
the transfer_history table for the bandwidth/ratio history charts, and prunes
old samples.
"""

import logging
from typing import List, Dict, Any, Optional

from app.db import get_pool
from app.services.download_clients.base import TorrentState

logger = logging.getLogger(__name__)

RETENTION_DAYS = 30


async def record_transfer_sample(client, torrents: Optional[List[Any]] = None) -> None:
    """Insert one transfer-stats sample and prune samples older than the retention window."""
    try:
        transfer = await client.get_transfer_info()
        if torrents is None:
            torrents = await client.get_torrents()

        downloading = sum(1 for t in torrents if t.state == TorrentState.DOWNLOADING)
        seeding = sum(1 for t in torrents if t.state == TorrentState.SEEDING)
        total_up = sum(t.uploaded or 0 for t in torrents)
        total_down = sum(t.downloaded or 0 for t in torrents)
        global_ratio = (total_up / total_down) if total_down > 0 else 0.0

        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO transfer_history (
                    download_speed, upload_speed, session_download, session_upload,
                    global_ratio, active_downloads, active_seeds
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                int(transfer.get("dl_info_speed", 0)),
                int(transfer.get("up_info_speed", 0)),
                int(transfer.get("dl_info_data", 0)),
                int(transfer.get("up_info_data", 0)),
                float(global_ratio),
                downloading,
                seeding,
            )
            await conn.execute(
                f"DELETE FROM transfer_history WHERE recorded_at < NOW() - INTERVAL '{RETENTION_DAYS} days'"
            )
    except Exception as e:
        logger.debug(f"Transfer-history sampling failed: {e}")


async def get_transfer_history(conn, hours: int, max_points: int = 300) -> List[Dict[str, Any]]:
    """
    Return time-bucketed transfer history for the last N hours. Bucket size scales
    with the range so the series stays around max_points.
    """
    bucket_seconds = max(60, (hours * 3600) // max_points)
    rows = await conn.fetch(
        """
        SELECT to_timestamp(floor(extract(epoch from recorded_at) / $1) * $1) AS bucket,
               AVG(download_speed)::bigint AS download_speed,
               AVG(upload_speed)::bigint AS upload_speed,
               MAX(global_ratio) AS global_ratio,
               MAX(active_downloads) AS active_downloads,
               MAX(active_seeds) AS active_seeds
        FROM transfer_history
        WHERE recorded_at > NOW() - ($2 * INTERVAL '1 hour')
        GROUP BY bucket
        ORDER BY bucket
        """,
        bucket_seconds,
        hours,
    )
    return [
        {
            "timestamp": r["bucket"].isoformat() if r["bucket"] else None,
            "download_speed": r["download_speed"] or 0,
            "upload_speed": r["upload_speed"] or 0,
            "global_ratio": float(r["global_ratio"] or 0),
            "active_downloads": r["active_downloads"] or 0,
            "active_seeds": r["active_seeds"] or 0,
        }
        for r in rows
    ]
