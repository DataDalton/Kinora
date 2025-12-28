import asyncio
import time
from datetime import datetime
from app.tasks.celery_app import celery_app, runAsync
from app.db import get_pool
from app.services.metadata.tmdb import tmdb_service
from app.core.cache import cacheSet


@celery_app.task(name="app.tasks.metadata_refresh.refresh_all_metadata")
def refresh_all_metadata():
    """Refresh metadata for items with missing data or upcoming status."""
    return runAsync(asyncRefreshAllMetadata())


async def asyncRefreshAllMetadata():
    """
    Smart metadata refresh that only updates:
    1. Items with missing critical data (poster or overview)
    2. Items with 'upcoming' or 'in production' status
    """
    taskName = "metadata_refresh"
    startTime = time.time()
    status = "success"
    updatedCount = 0
    errors = []

    try:
        pool = await get_pool()

        async with pool.acquire() as conn:
            # 1. Movies with missing critical data
            missingDataMovies = await conn.fetch("""
                SELECT id, tmdb_id FROM movies
                WHERE tmdb_id IS NOT NULL
                AND (poster_path IS NULL OR overview IS NULL OR overview = '')
                LIMIT 20
            """)

            # 2. Movies with upcoming or in production status
            upcomingMovies = await conn.fetch("""
                SELECT id, tmdb_id FROM movies
                WHERE tmdb_id IS NOT NULL
                AND status IN ('Upcoming', 'In Production', 'Planned', 'Post Production', 'Rumored')
                LIMIT 20
            """)

            # Combine and deduplicate
            movieIds = set()
            moviesToRefresh = []
            for movie in list(missingDataMovies) + list(upcomingMovies):
                if movie["id"] not in movieIds:
                    movieIds.add(movie["id"])
                    moviesToRefresh.append(movie)

            # Refresh each movie with rate limiting
            for movie in moviesToRefresh:
                try:
                    tmdbData = await tmdb_service.get_movie(movie["tmdb_id"])
                    if tmdbData:
                        parsedData = tmdb_service.parse_movie_data(tmdbData)

                        await conn.execute("""
                            UPDATE movies SET
                                overview = COALESCE($2, overview),
                                poster_path = COALESCE($3, poster_path),
                                backdrop_path = COALESCE($4, backdrop_path),
                                status = COALESCE($5, status),
                                rating = COALESCE($6, rating),
                                updated_at = NOW()
                            WHERE id = $1
                        """,
                            movie["id"],
                            parsedData.get("overview"),
                            parsedData.get("poster_path"),
                            parsedData.get("backdrop_path"),
                            tmdbData.get("status"),
                            parsedData.get("rating"),
                        )
                        updatedCount += 1

                    await asyncio.sleep(0.5)  # Rate limiting
                except Exception as e:
                    errors.append(f"Movie {movie['id']}: {str(e)}")

            # Similar for shows with missing data
            missingDataShows = await conn.fetch("""
                SELECT id, tmdb_id FROM shows
                WHERE tmdb_id IS NOT NULL
                AND (poster_path IS NULL OR overview IS NULL OR overview = '')
                LIMIT 20
            """)

            upcomingShows = await conn.fetch("""
                SELECT id, tmdb_id FROM shows
                WHERE tmdb_id IS NOT NULL
                AND status IN ('Returning Series', 'In Production', 'Planned', 'Pilot')
                LIMIT 20
            """)

            showIds = set()
            showsToRefresh = []
            for show in list(missingDataShows) + list(upcomingShows):
                if show["id"] not in showIds:
                    showIds.add(show["id"])
                    showsToRefresh.append(show)

            for show in showsToRefresh:
                try:
                    tmdbData = await tmdb_service.get_tv(show["tmdb_id"])
                    if tmdbData:
                        parsedData = tmdb_service.parse_tv_data(tmdbData)

                        await conn.execute("""
                            UPDATE shows SET
                                overview = COALESCE($2, overview),
                                poster_path = COALESCE($3, poster_path),
                                backdrop_path = COALESCE($4, backdrop_path),
                                status = COALESCE($5, status),
                                rating = COALESCE($6, rating),
                                updated_at = NOW()
                            WHERE id = $1
                        """,
                            show["id"],
                            parsedData.get("overview"),
                            parsedData.get("poster_path"),
                            parsedData.get("backdrop_path"),
                            tmdbData.get("status"),
                            parsedData.get("rating"),
                        )
                        updatedCount += 1

                    await asyncio.sleep(0.5)
                except Exception as e:
                    errors.append(f"Show {show['id']}: {str(e)}")

        return {
            "status": "success",
            "itemsUpdated": updatedCount,
            "errors": errors[:10],
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    except Exception as e:
        status = "failed"
        print(f"Metadata refresh error: {e}")
        return {"status": "error", "message": str(e), "errors": errors[:10]}

    finally:
        elapsedMs = int((time.time() - startTime) * 1000)
        await cacheSet(f"task:last_run:{taskName}", {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "status": status,
            "durationMs": elapsedMs,
        }, expire=86400)
