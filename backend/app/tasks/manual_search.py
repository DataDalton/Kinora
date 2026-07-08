"""
Per-item automated search.

Runs the profile-driven cascading search for a single media item and grabs the best
release, honoring that item's blocklist. Used by the "Blocklist and search again" action so
a replacement is found without waiting for the next scheduled search cycle.
"""

from app.tasks.celery_app import celery_app, runAsync
from app.db import get_pool
from app.services.automation.search_engine import search_engine
from app.services.media_profile import MediaProfile


@celery_app.task(name="app.tasks.manual_search.search_media_item")
def search_media_item(media_type: str, media_id: int):
    """Search indexers for a single item and grab the best allowed release."""
    return runAsync(async_search_media_item(media_type, media_id))


# (table, category, year_column)
_VIDEO_TYPES = {
    "movie": ("movies", "movies", "release_date"),
    "show": ("shows", "tv", "first_air_date"),
    "anime": ("anime", "anime", "season_year"),
}


def _year_of(value):
    if not value:
        return None
    return value.year if hasattr(value, "year") else value


async def async_search_media_item(media_type: str, media_id: int):
    normalized = "album" if media_type in ("music", "track", "album") else media_type

    pool = await get_pool()
    async with pool.acquire() as conn:
        if normalized in _VIDEO_TYPES:
            table, category, year_col = _VIDEO_TYPES[normalized]
            row = await conn.fetchrow(
                f"SELECT id, title, {year_col} AS year_src, media_profile_id FROM {table} WHERE id = $1",
                media_id,
            )
            if not row or not row["media_profile_id"]:
                return {"status": "skipped", "reason": "Item or profile not found"}

            profile_row = await conn.fetchrow("SELECT * FROM media_profiles WHERE id = $1", row["media_profile_id"])
            if not profile_row:
                return {"status": "skipped", "reason": "Profile not found"}
            profile = MediaProfile.from_row(dict(profile_row))

            query = row["title"]
            year = _year_of(row["year_src"])
            if normalized == "movie" and year:
                query += f" {year}"

            torrent_hash = await search_engine.search_and_download(
                query=query,
                profile=profile,
                category=category,
                tags=["kinora", f"{normalized}-{media_id}"],
                media_type=normalized,
                history_conn=conn,
                history_media_id=media_id,
            )
            if torrent_hash:
                await conn.execute(
                    f"UPDATE {table} SET status = 'downloading', updated_at = NOW() WHERE id = $1",
                    media_id,
                )
                return {"status": "success", "torrent_hash": torrent_hash}
            return {"status": "success", "reason": "No acceptable release found"}

        if normalized == "album":
            album = await conn.fetchrow(
                """
                SELECT a.id, a.title, a.media_profile_id,
                       ar.name AS artist_name
                FROM albums a
                LEFT JOIN artists ar ON a.artist_id = ar.id
                WHERE a.id = $1
                """,
                media_id,
            )
            if not album or not album["media_profile_id"]:
                return {"status": "skipped", "reason": "Album or profile not found"}

            profile_row = await conn.fetchrow("SELECT * FROM media_profiles WHERE id = $1", album["media_profile_id"])
            if not profile_row:
                return {"status": "skipped", "reason": "Profile not found"}
            profile = MediaProfile.from_row(dict(profile_row))

            artist_name = album["artist_name"] or ""
            query = f"{artist_name} {album['title']}".strip()

            torrent_hash = await search_engine.search_music_and_download(
                query=query,
                profile=profile,
                tags=["kinora", f"album-{media_id}"],
                history_conn=conn,
                history_media_id=media_id,
            )
            if torrent_hash:
                await conn.execute(
                    "UPDATE albums SET status = 'downloading', updated_at = NOW() WHERE id = $1",
                    media_id,
                )
                return {"status": "success", "torrent_hash": torrent_hash}
            return {"status": "success", "reason": "No acceptable release found"}

        return {"status": "skipped", "reason": f"Unsupported media type: {media_type}"}
