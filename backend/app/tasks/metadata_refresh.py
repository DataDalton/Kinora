import asyncio
import time
from datetime import datetime
from app.tasks.celery_app import celery_app, runAsync
from app.db import get_pool
from app.services.metadata.tmdb import tmdb_service
from app.core.cache import cacheSet

# Movies released within this many days, and not yet in the library, have their digital
# and physical dates rechecked, since TMDB usually adds those after the cinema release.
RELEASE_DATE_RECHECK_DAYS = 365


@celery_app.task(name="app.tasks.metadata_refresh.recompute_release_dates")
def recompute_release_dates():
    """Recompute every movie's digital, physical and theatrical dates for the current release region."""
    return runAsync(asyncRecomputeReleaseDates())


async def asyncRecomputeReleaseDates():
    """
    Rewrite the stored release dates of every movie from TMDB's release_dates block,
    picked for the current release region. Runs after the region setting changes, since
    stored dates belong to the region that was set when they were fetched. Movie details
    are usually served from the TMDB cache, so only uncached movies reach the network.
    """
    tmdb_service.invalidateReleaseRegion()
    region = await tmdb_service.getReleaseRegion()
    updatedCount = 0
    pool = await get_pool()
    async with pool.acquire() as conn:
        movies = await conn.fetch("SELECT id, tmdb_id FROM movies WHERE tmdb_id IS NOT NULL ORDER BY id")
        for movie in movies:
            try:
                tmdbData = await tmdb_service.get_movie(movie["tmdb_id"])
                if not tmdbData or "release_dates" not in tmdbData:
                    continue
                dates = tmdb_service.parseReleaseDates(tmdbData, region)
                await conn.execute(
                    """
                    UPDATE movies SET
                        digital_release_date = $2,
                        physical_release_date = $3,
                        theatrical_release_date = $4,
                        updated_at = NOW()
                    WHERE id = $1
                    """,
                    movie["id"],
                    dates["digital_release_date"],
                    dates["physical_release_date"],
                    dates["theatrical_release_date"],
                )
                updatedCount += 1
                await asyncio.sleep(0.1)  # Spaces out TMDB requests for movies missing from the cache
            except Exception as e:
                print(f"Error recomputing release dates for movie {movie['id']}: {e}")
    print(f"Recomputed release dates for {updatedCount} movies in region {region}")
    return {"region": region, "updated": updatedCount}


@celery_app.task(name="app.tasks.metadata_refresh.refresh_all_metadata")
def refresh_all_metadata():
    """Refresh metadata for items with missing data or upcoming status."""
    return runAsync(asyncRefreshAllMetadata())


async def asyncRefreshAllMetadata():
    """
    Metadata refresh that only updates:
    1. Items with missing critical data (poster or overview)
    2. Items whose TMDB status says they are not finished (upcoming, in production,
       returning), or that have no TMDB status stored yet
    3. Movies without a file that are recent or unreleased and still lack a digital or
       physical release date
    TMDB's status is stored in metadata_status. The status column holds Kinora's own
    state (wanted, downloading, completed) and is never written here.
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

            # 2. Movies TMDB has not marked released, and movies with no TMDB status yet
            upcomingMovies = await conn.fetch("""
                SELECT id, tmdb_id FROM movies
                WHERE tmdb_id IS NOT NULL
                AND (metadata_status IS NULL
                     OR metadata_status IN ('Upcoming', 'In Production', 'Planned', 'Post Production', 'Rumored'))
                ORDER BY updated_at ASC
                LIMIT 20
            """)

            # 3. Movies whose digital or physical date may still appear on TMDB
            releaseDateMovies = await conn.fetch(f"""
                SELECT id, tmdb_id FROM movies
                WHERE tmdb_id IS NOT NULL
                AND has_file = FALSE
                AND (digital_release_date IS NULL OR physical_release_date IS NULL)
                AND (release_date IS NULL OR release_date > NOW() - INTERVAL '{RELEASE_DATE_RECHECK_DAYS} days')
                ORDER BY updated_at ASC
                LIMIT 20
            """)

            # Combine and deduplicate
            movieIds = set()
            moviesToRefresh = []
            for movie in list(missingDataMovies) + list(upcomingMovies) + list(releaseDateMovies):
                if movie["id"] not in movieIds:
                    movieIds.add(movie["id"])
                    moviesToRefresh.append(movie)

            # Refresh each movie with rate limiting
            for movie in moviesToRefresh:
                try:
                    tmdbData = await tmdb_service.get_movie(movie["tmdb_id"])
                    if tmdbData:
                        parsedData = tmdb_service.parse_movie_data(tmdbData)

                        await conn.execute(
                            """
                            UPDATE movies SET
                                overview = COALESCE($2, overview),
                                poster_path = COALESCE($3, poster_path),
                                backdrop_path = COALESCE($4, backdrop_path),
                                metadata_status = COALESCE($5, metadata_status),
                                rating = COALESCE($6, rating),
                                release_date = COALESCE($7, release_date),
                                digital_release_date = COALESCE($8, digital_release_date),
                                physical_release_date = COALESCE($9, physical_release_date),
                                theatrical_release_date = COALESCE($10, theatrical_release_date),
                                updated_at = NOW()
                            WHERE id = $1
                        """,
                            movie["id"],
                            parsedData.get("overview"),
                            parsedData.get("poster_path"),
                            parsedData.get("backdrop_path"),
                            tmdbData.get("status"),
                            parsedData.get("rating"),
                            parsedData.get("release_date"),
                            parsedData.get("digital_release_date"),
                            parsedData.get("physical_release_date"),
                            parsedData.get("theatrical_release_date"),
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

            # Shows still airing or not started, and shows with no TMDB status yet
            upcomingShows = await conn.fetch("""
                SELECT id, tmdb_id FROM shows
                WHERE tmdb_id IS NOT NULL
                AND (metadata_status IS NULL
                     OR metadata_status IN ('Returning Series', 'In Production', 'Planned', 'Pilot'))
                ORDER BY updated_at ASC
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

                        await conn.execute(
                            """
                            UPDATE shows SET
                                overview = COALESCE($2, overview),
                                poster_path = COALESCE($3, poster_path),
                                backdrop_path = COALESCE($4, backdrop_path),
                                metadata_status = COALESCE($5, metadata_status),
                                rating = COALESCE($6, rating),
                                in_production = COALESCE($7, in_production),
                                last_air_date = COALESCE($8, last_air_date),
                                number_of_seasons = COALESCE($9, number_of_seasons),
                                number_of_episodes = COALESCE($10, number_of_episodes),
                                updated_at = NOW()
                            WHERE id = $1
                        """,
                            show["id"],
                            parsedData.get("overview"),
                            parsedData.get("poster_path"),
                            parsedData.get("backdrop_path"),
                            tmdbData.get("status"),
                            parsedData.get("rating"),
                            parsedData.get("in_production"),
                            parsedData.get("last_air_date"),
                            parsedData.get("number_of_seasons"),
                            parsedData.get("number_of_episodes"),
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
        await cacheSet(
            f"task:last_run:{taskName}",
            {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "status": status,
                "durationMs": elapsedMs,
            },
            expire=86400,
        )
