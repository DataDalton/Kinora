import asyncio
import time
from datetime import datetime

from app.tasks.celery_app import celery_app, runAsync
from app.db import get_pool
from app.services.automation.search_engine import search_engine
from app.services.media_profile import MediaProfile
from app.core.cache import cacheSet

# (media_type, table, category, year_column)
_UPGRADE_TYPES = (
    ("movie", "movies", "movies", "release_date"),
    ("show", "shows", "tv", "first_air_date"),
    ("anime", "anime", "anime", "season_year"),
)


@celery_app.task(name="app.tasks.upgrade_search.search_upgrades")
def search_upgrades():
    """
    Search for higher-quality releases of items that already have a file and whose
    effective upgrade_allowed (item override, else profile) is TRUE.
    """
    return runAsync(async_search_upgrades())


def _query_year(year_src):
    if not year_src:
        return None
    return year_src.year if hasattr(year_src, "year") else year_src


async def async_search_upgrades():
    taskName = "upgrade_search"
    startTime = time.time()
    status = "success"

    try:
        grabbed = 0
        pool = await get_pool()

        async with pool.acquire() as conn:
            for media_type, table, category, year_col in _UPGRADE_TYPES:
                rows = await conn.fetch(f"""
                    SELECT t.id, t.title, t.media_profile_id, t.quality_detected,
                           t.{year_col} AS year_src,
                           COALESCE(t.upgrade_allowed, mp.upgrade_allowed) AS effective_upgrade
                    FROM {table} t
                    INNER JOIN media_profiles mp ON t.media_profile_id = mp.id
                    WHERE t.monitored = TRUE AND t.has_file = TRUE
                      AND t.status NOT IN ('downloading', 'processing')
                      AND COALESCE(t.upgrade_allowed, mp.upgrade_allowed) = TRUE
                      AND t.quality_detected IS NOT NULL
                    LIMIT 50
                    """)
                if not rows:
                    continue

                profileIds = list({r["media_profile_id"] for r in rows})
                profileRows = await conn.fetch("SELECT * FROM media_profiles WHERE id = ANY($1)", profileIds)
                profiles = {r["id"]: MediaProfile.from_row(dict(r)) for r in profileRows}

                for row in rows:
                    item = dict(row)
                    profile = profiles.get(item["media_profile_id"])
                    if not profile:
                        continue

                    query = item["title"]
                    year = _query_year(item.get("year_src"))
                    if media_type == "movie" and year:
                        query += f" {year}"

                    try:
                        torrent_hash = await search_engine.search_and_download(
                            query=query,
                            profile=profile,
                            category=category,
                            tags=["kinora", f"{media_type}-{item['id']}"],
                            media_type=media_type,
                            history_conn=conn,
                            history_media_id=item["id"],
                            current_quality=item["quality_detected"],
                            grab_mode="upgrade",
                            upgrade_allowed=item["effective_upgrade"],
                        )
                        if torrent_hash:
                            await conn.execute(
                                f"UPDATE {table} SET status = 'downloading', updated_at = NOW() WHERE id = $1",
                                item["id"],
                            )
                            grabbed += 1
                    except Exception as e:
                        print(f"Upgrade search error for {query}: {e}")

                    await asyncio.sleep(2)

        return {
            "status": "success",
            "upgrades_grabbed": grabbed,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    except Exception as e:
        status = "failed"
        print(f"Upgrade search error: {e}")
        return {"status": "error", "message": str(e)}

    finally:
        elapsedMs = int((time.time() - startTime) * 1000)
        await cacheSet(
            f"task:last_run:{taskName}",
            {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "status": status,
                "durationMs": elapsedMs,
            },
            expire=86400,
        )
