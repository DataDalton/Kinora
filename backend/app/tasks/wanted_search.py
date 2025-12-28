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
            wantedMoviesWithProfiles = await conn.fetch(
                """
                SELECT m.id, m.title, m.release_date, m.media_profile_id,
                       mp.id as mp_id, mp.name as mp_name, mp.resolutions,
                       mp.sources, mp.codecs, mp.uploaders, mp.min_seeds,
                       mp.min_size, mp.max_size, mp.search_timeout, mp.max_results
                FROM movies m
                INNER JOIN media_profiles mp ON m.media_profile_id = mp.id
                WHERE m.monitored = TRUE AND m.has_file = FALSE
                  AND m.status NOT IN ('downloading', 'processing')
                ORDER BY m.popularity DESC NULLS LAST
                LIMIT 50
                """
            )

            for row in wantedMoviesWithProfiles:
                movie = dict(row)
                searched_count += 1

                # Build search query
                query = movie["title"]
                if movie["release_date"]:
                    query += f" {movie['release_date'].year}"

                # Construct MediaProfile from joined columns
                profileData = {
                    "id": movie["mp_id"],
                    "name": movie["mp_name"],
                    "resolutions": movie["resolutions"],
                    "sources": movie["sources"],
                    "codecs": movie["codecs"],
                    "uploaders": movie["uploaders"],
                    "min_seeds": movie["min_seeds"],
                    "min_size": movie["min_size"],
                    "max_size": movie["max_size"],
                    "search_timeout": movie["search_timeout"],
                    "max_results": movie["max_results"],
                }
                profile = MediaProfile(**profileData)

                # Search and download
                try:
                    torrent_hash = await search_engine.search_and_download(
                        query=query,
                        profile=profile,
                        category="movies",
                        tags=["nexarr", f"movie-{movie['id']}"],
                    )

                    if torrent_hash:
                        # Record download
                        await conn.execute(
                            """
                            INSERT INTO download_history (
                                media_id, media_type, torrent_hash, torrent_title,
                                indexer, status, download_client
                            )
                            VALUES ($1, $2, $3, $4, $5, $6, $7)
                            """,
                            movie["id"], "movie", torrent_hash, query,
                            "multiple", "downloading", "qbittorrent"
                        )

                        # Update movie status
                        await conn.execute(
                            """
                            UPDATE movies
                            SET status = 'downloading', updated_at = NOW()
                            WHERE id = $1
                            """,
                            movie["id"]
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
        await cacheSet(f"task:last_run:{taskName}", {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "status": status,
            "durationMs": elapsedMs,
        }, expire=86400)
