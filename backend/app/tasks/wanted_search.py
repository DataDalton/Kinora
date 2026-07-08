import asyncio
import time
from datetime import datetime
from app.tasks.celery_app import celery_app, runAsync
from app.db import get_pool
from app.services.automation.search_engine import search_engine
from app.services.media_profile import MediaProfile
from app.core.cache import cacheSet


@celery_app.task(name="app.tasks.wanted_search.search_wanted_media")
def search_wanted_media():
    """
    Search for all wanted/missing media across indexers
    Automatically selects and grabs best matches
    """
    return runAsync(async_search_wanted_media())


async def async_search_wanted_media():
    """
    Async implementation of wanted search
    """
    taskName = "wanted_search"
    startTime = time.time()
    status = "success"

    try:
        grabbed_count = 0
        searched_count = 0

        pool = await get_pool()

        async with pool.acquire() as conn:
            # Get all wanted movies with their media profiles using JOIN
            wantedMoviesWithProfiles = await conn.fetch("""
                SELECT m.id, m.title, m.release_date, m.media_profile_id
                FROM movies m
                INNER JOIN media_profiles mp ON m.media_profile_id = mp.id
                WHERE m.monitored = TRUE AND m.has_file = FALSE
                  AND m.status NOT IN ('downloading', 'processing')
                ORDER BY m.popularity DESC NULLS LAST
                LIMIT 50
                """)

            # Batch-load the referenced profiles in one query, then look them up per movie.
            profileIds = list({m["media_profile_id"] for m in wantedMoviesWithProfiles})
            profileRows = await conn.fetch("SELECT * FROM media_profiles WHERE id = ANY($1)", profileIds)
            profiles = {r["id"]: MediaProfile.from_row(dict(r)) for r in profileRows}

            for row in wantedMoviesWithProfiles:
                movie = dict(row)
                searched_count += 1

                # Build search query
                query = movie["title"]
                if movie["release_date"]:
                    query += f" {movie['release_date'].year}"

                profile = profiles.get(movie["media_profile_id"])
                if not profile:
                    continue

                # Search and download
                try:
                    torrent_hash = await search_engine.search_and_download(
                        query=query,
                        profile=profile,
                        category="movies",
                        tags=["kinora", f"movie-{movie['id']}"],
                        media_type="movie",
                        history_conn=conn,
                        history_media_id=movie["id"],
                    )

                    if torrent_hash:
                        # The engine records download_history (with re-addable source).
                        # Update movie status here.
                        await conn.execute(
                            """
                            UPDATE movies
                            SET status = 'downloading', updated_at = NOW()
                            WHERE id = $1
                            """,
                            movie["id"],
                        )

                        grabbed_count += 1

                except Exception as e:
                    print(f"Error searching for {query}: {e}")
                    continue

                # Small delay to avoid hammering indexers
                await asyncio.sleep(2)

        return {
            "status": "success",
            "items_searched": searched_count,
            "items_grabbed": grabbed_count,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    except Exception as e:
        status = "failed"
        print(f"Wanted search error: {e}")
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
