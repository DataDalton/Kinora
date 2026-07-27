"""
Warm-set metadata prefetch.

Refreshes the metadata every browse page opens with (trending, popular, upcoming,
top rated, default discover pages, charts) on a schedule, so those requests are
answered from cache and never wait on a provider. Runs through the normal service
methods, which handle both cache tiers.
"""

import asyncio
import time
from datetime import datetime

from app.tasks.celery_app import celery_app, runAsync
from app.services.metadata.tmdb import tmdb_service
from app.services.metadata.anilist import anilist_service
from app.services.metadata.deezer import deezer_service
from app.services import metadata_cache
from app.core.cache import cacheSet


@celery_app.task(name="app.tasks.metadata_prefetch.prefetch_warm_sets")
def prefetch_warm_sets():
    """Prefetch the browse-page metadata sets."""
    return runAsync(async_prefetch_warm_sets())


async def async_prefetch_warm_sets():
    taskName = "metadata_prefetch"
    startTime = time.time()
    status = "success"

    names_and_fetchers = [
        ("tmdb_trending", tmdb_service.get_trending("all", "week")),
        ("tmdb_popular_movies", tmdb_service.get_popular("movie")),
        ("tmdb_popular_tv", tmdb_service.get_popular("tv")),
        ("tmdb_upcoming", tmdb_service.get_upcoming()),
        ("tmdb_top_rated_movies", tmdb_service.get_top_rated("movie")),
        ("tmdb_top_rated_tv", tmdb_service.get_top_rated("tv")),
        ("tmdb_discover_movies", tmdb_service.discover_movies()),
        ("tmdb_discover_tv", tmdb_service.discover_tv()),
        ("anilist_trending", anilist_service.get_trending(per_page=20)),
        ("deezer_chart", deezer_service.get_chart()),
        ("deezer_new_releases", deezer_service.get_editorial_releases()),
    ]

    try:
        results = await asyncio.gather(
            *(fetcher for _name, fetcher in names_and_fetchers),
            return_exceptions=True,
        )

        warmed = []
        failed = []
        for (name, _fetcher), result in zip(names_and_fetchers, results):
            if isinstance(result, Exception):
                failed.append(name)
                print(f"Warm-set prefetch failed for {name}: {result}")
            else:
                warmed.append(name)

        if failed and not warmed:
            status = "failed"

        # Housekeeping: drop persistent rows nothing has refreshed in the
        # retention window.
        removed = await metadata_cache.cleanupStale()

        return {
            "status": status,
            "warmed": warmed,
            "failed": failed,
            "stale_rows_removed": removed,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    except Exception as e:
        status = "failed"
        print(f"Warm-set prefetch error: {e}")
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
