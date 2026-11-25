"""
Keeps a library item's status in step with its downloads.

An item is set to 'downloading' when a release is sent to the download client. When that
download goes away without importing, the item has to leave 'downloading' or the library
keeps showing it as in progress.
"""

import asyncpg

MEDIA_TABLES = {
    "movie": "movies",
    "show": "shows",
    "anime": "anime",
    "album": "albums",
}

ACTIVE_DOWNLOAD_STATUSES = ("downloading", "pending", "processing")


async def itemHasFile(conn: asyncpg.Connection, mediaType: str, mediaId: int) -> bool:
    """
    Whether an item has any file in the library. Shows track files per episode, and
    anime per episode as well as on the anime row.
    """
    if mediaType == "show":
        sql = "SELECT EXISTS (SELECT 1 FROM episodes WHERE show_id = $1 AND has_file)"
    elif mediaType == "anime":
        sql = (
            "SELECT COALESCE((SELECT has_file FROM anime WHERE id = $1), FALSE) "
            "OR EXISTS (SELECT 1 FROM anime_episodes WHERE anime_id = $1 AND has_file)"
        )
    else:
        table = MEDIA_TABLES.get(mediaType)
        if table is None:
            return False
        sql = f"SELECT COALESCE((SELECT has_file FROM {table} WHERE id = $1), FALSE)"
    return bool(await conn.fetchval(sql, mediaId))


async def releaseDownloadingStatus(conn: asyncpg.Connection, mediaType: str, mediaId: int) -> None:
    """
    Move an item out of 'downloading' once none of its downloads are active. It returns
    to 'completed' when it already has a file, such as a removed upgrade, and to 'wanted'
    otherwise. An item in any other status is left alone.
    """
    table = MEDIA_TABLES.get(mediaType)
    if table is None or mediaId is None:
        return

    stillActive = await conn.fetchval(
        "SELECT 1 FROM download_history WHERE media_type = $1 AND media_id = $2 AND status = ANY($3::text[]) LIMIT 1",
        mediaType,
        mediaId,
        list(ACTIVE_DOWNLOAD_STATUSES),
    )
    if stillActive:
        return

    hasFile = await itemHasFile(conn, mediaType, mediaId)
    await conn.execute(
        f"UPDATE {table} SET status = $2, updated_at = NOW() WHERE id = $1 AND status = 'downloading'",
        mediaId,
        "completed" if hasFile else "wanted",
    )
