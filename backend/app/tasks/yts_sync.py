"""
YTS catalog mirror.

Pages politely through the YTS API and upserts every torrent into the local
release index, so YTS "searches" become local SQL queries instead of API calls.
The first runs perform a resumable full crawl in bounded chunks, after which each
run is a small delta pull of newly added movies. All progress is persisted in
app_settings, so restarts and failures resume where they left off.
"""

import asyncio
import json
import time
from datetime import datetime

from app.tasks.celery_app import celery_app, runAsync
from app.db import get_pool
from app.core.cache import cacheSet
from app.core.http_client import http_get
from app.services import release_index
from app.services.indexers.yts import yts_indexer

STATE_KEY = "yts_sync_state"

# Movies per API page (YTS maximum).
PAGE_SIZE = 50

# Pages fetched per run during the full crawl, bounding each run to a few minutes.
MAX_FULL_PAGES_PER_RUN = 300

# Safety cap on delta pages per run. 20 pages = 1000 newest movies.
MAX_DELTA_PAGES = 20

# Pause between page requests so the crawl never hammers the API.
REQUEST_DELAY_SECONDS = 1.0


@celery_app.task(name="app.tasks.yts_sync.sync_yts_catalog", time_limit=1800, soft_time_limit=1680)
def sync_yts_catalog():
    """Continue the full YTS crawl or pull the daily delta into the release index."""
    return runAsync(async_sync_yts_catalog())


async def _load_state(conn) -> dict:
    raw = await conn.fetchval("SELECT value FROM app_settings WHERE key = $1", STATE_KEY)
    if raw:
        try:
            state = json.loads(raw)
            if isinstance(state, dict):
                return state
        except json.JSONDecodeError:
            pass
    return {"full_sync_done": False, "cursor_page": 1, "highest_movie_id": 0, "last_synced_at": None}


async def _save_state(conn, state: dict) -> None:
    await conn.execute(
        """
        INSERT INTO app_settings (key, value, value_type, is_encrypted, category, description)
        VALUES ($1, $2, 'json', FALSE, 'system', 'YTS catalog mirror progress')
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
        """,
        STATE_KEY,
        json.dumps(state),
    )


async def _fetch_page(page: int, order_by: str) -> list:
    """One page of the YTS catalog as raw movie dicts. Raises on HTTP failure."""
    response = await http_get(
        f"{yts_indexer.current_api_url}/list_movies.json",
        params={
            "limit": PAGE_SIZE,
            "page": page,
            "sort_by": "date_added",
            "order_by": order_by,
        },
    )
    response.raise_for_status()
    data = response.json()
    if data.get("status") != "ok":
        raise RuntimeError(f"YTS API returned status {data.get('status')}")
    return data.get("data", {}).get("movies", []) or []


def _movies_to_releases(movies: list) -> tuple:
    """Parse raw movie dicts into releases. Returns (releases, highest_movie_id)."""
    releases = []
    highest_id = 0
    for movie in movies:
        movie_id = movie.get("id") or 0
        highest_id = max(highest_id, movie_id)
        try:
            releases.extend(yts_indexer._parse_movie(movie))
        except Exception as e:
            print(f"YTS sync could not parse movie {movie_id}: {e}")
    return releases, highest_id


async def async_sync_yts_catalog():
    taskName = "yts_sync"
    startTime = time.time()
    status = "success"
    pages_fetched = 0
    releases_written = 0

    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            state = await _load_state(conn)

        if not state.get("full_sync_done"):
            # Full crawl chunk, oldest first so page contents stay stable while new
            # movies append to the end of the catalog.
            page = int(state.get("cursor_page") or 1)
            last_page_of_run = page + MAX_FULL_PAGES_PER_RUN - 1

            while page <= last_page_of_run:
                movies = await _fetch_page(page, order_by="asc")
                pages_fetched += 1

                if movies:
                    releases, highest_id = _movies_to_releases(movies)
                    releases_written += await release_index.upsertReleases(releases)
                    state["highest_movie_id"] = max(int(state.get("highest_movie_id") or 0), highest_id)

                if len(movies) < PAGE_SIZE:
                    # Reached the end of the catalog.
                    state["full_sync_done"] = True
                    state["cursor_page"] = page
                    break

                page += 1
                state["cursor_page"] = page

                # Persist progress every 25 pages so an interrupted run resumes nearby.
                if pages_fetched % 25 == 0:
                    state["last_synced_at"] = datetime.utcnow().isoformat() + "Z"
                    async with pool.acquire() as conn:
                        await _save_state(conn, state)

                await asyncio.sleep(REQUEST_DELAY_SECONDS)

            phase = "full" if not state["full_sync_done"] else "full-completed"

        else:
            # Delta pull: newest first, stop at the first fully known page. YTS ids
            # grow with addition time, so id order tracks date_added order.
            known_highest = int(state.get("highest_movie_id") or 0)
            new_highest = known_highest

            for page in range(1, MAX_DELTA_PAGES + 1):
                movies = await _fetch_page(page, order_by="desc")
                pages_fetched += 1

                if not movies:
                    break

                fresh = [m for m in movies if (m.get("id") or 0) > known_highest]
                if fresh:
                    releases, highest_id = _movies_to_releases(fresh)
                    releases_written += await release_index.upsertReleases(releases)
                    new_highest = max(new_highest, highest_id)

                if len(fresh) < len(movies):
                    # This page reached into already-known movies, done.
                    break

                await asyncio.sleep(REQUEST_DELAY_SECONDS)

            state["highest_movie_id"] = new_highest
            phase = "delta"

        state["last_synced_at"] = datetime.utcnow().isoformat() + "Z"
        async with pool.acquire() as conn:
            await _save_state(conn, state)

        return {
            "status": "success",
            "phase": phase,
            "pages_fetched": pages_fetched,
            "releases_written": releases_written,
            "full_sync_done": state.get("full_sync_done", False),
            "cursor_page": state.get("cursor_page"),
            "highest_movie_id": state.get("highest_movie_id"),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    except Exception as e:
        status = "failed"
        print(f"YTS sync error: {e}")
        return {"status": "error", "message": str(e), "pages_fetched": pages_fetched}

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
