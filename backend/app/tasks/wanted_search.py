import asyncio
from datetime import datetime
from app.tasks.celery_app import celery_app
from app.core.database import get_pool
from app.services.automation.search_engine import search_engine
from app.services.media_profile import MediaProfile


@celery_app.task(name="app.tasks.wanted_search.search_wanted_media")
def search_wanted_media():
    """
    Search for all wanted/missing media across indexers
    Automatically selects and grabs best matches
    """
    return asyncio.run(async_search_wanted_media())


async def async_search_wanted_media():
    """
    Async implementation of wanted search
    """
    try:
        grabbed_count = 0
        searched_count = 0

        pool = await get_pool()

        async with pool.acquire() as conn:
            # Get all wanted movies (monitored but no file)
            wanted_movies = await conn.fetch(
                """
                SELECT * FROM movies
                WHERE monitored = TRUE
                AND has_file = FALSE
                AND status NOT IN ('downloading', 'processing')
                ORDER BY popularity DESC NULLS LAST
                LIMIT 50
                """
            )

            for movie_row in wanted_movies:
                movie = dict(movie_row)
                searched_count += 1

                # Build search query
                query = movie["title"]
                if movie["release_date"]:
                    query += f" {movie['release_date'].year}"

                # Get quality profile
                if not movie["media_profile_id"]:
                    continue

                profile_row = await conn.fetchrow(
                    "SELECT * FROM quality_profiles WHERE id = $1",
                    movie["media_profile_id"]
                )

                if not profile_row:
                    continue

                profile = MediaProfile(**dict(profile_row))

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
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        print(f"Wanted search error: {e}")
        return {"status": "error", "message": str(e)}
