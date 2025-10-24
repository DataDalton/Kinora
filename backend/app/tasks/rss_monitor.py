import asyncio
from datetime import datetime
from app.tasks.celery_app import celery_app
from app.core.database import get_pool
from app.services.automation.search_engine import search_engine
from app.services.media_profile import MediaProfile, media_profile_service
from app.services.download_clients.qbittorrent import qbittorrent_client
from app.core.webtransport import webtransport_manager


@celery_app.task(name="app.tasks.rss_monitor.monitor_rss_feeds")
def monitor_rss_feeds():
    """
    Monitor RSS feeds from all enabled indexers
    Checks for new releases and auto-grabs matching wanted media
    """
    return asyncio.run(async_monitor_rss_feeds())


async def async_monitor_rss_feeds():
    """
    Async implementation of RSS monitoring
    """
    try:
        # Get recent releases from all indexers
        releases = await search_engine.get_rss_updates()

        if not releases:
            return {"status": "success", "releases_found": 0, "grabbed": 0}

        grabbed_count = 0
        pool = await get_pool()

        async with pool.acquire() as conn:
            # Get all monitored media
            monitored_movies = await conn.fetch(
                "SELECT * FROM movies WHERE monitored = TRUE AND has_file = FALSE"
            )

            monitored_shows = await conn.fetch(
                "SELECT * FROM shows WHERE monitored = TRUE"
            )

            # Check each release against wanted media
            for release in releases:
                # Try to match against movies
                for movie in monitored_movies:
                    movie_dict = dict(movie)
                    if await check_and_grab_movie(conn, release, movie_dict):
                        grabbed_count += 1
                        break

                # Try to match against shows
                for show in monitored_shows:
                    show_dict = dict(show)
                    if await check_and_grab_show(conn, release, show_dict):
                        grabbed_count += 1
                        break

        # Notify active users of RSS update
        active_users = webtransport_manager.get_active_users()
        for user_id in active_users:
            await webtransport_manager.send_rss_update(user_id, grabbed_count)

        return {
            "status": "success",
            "releases_found": len(releases),
            "grabbed": grabbed_count,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        print(f"RSS monitoring error: {e}")
        return {"status": "error", "message": str(e)}


async def check_and_grab_movie(conn, release, movie):
    """
    Check if release matches wanted movie and grab it
    """
    # Simple title matching (can be enhanced with fuzzy matching)
    release_title_lower = release.title.lower()
    movie_title_lower = movie["title"].lower()

    if movie_title_lower not in release_title_lower:
        return False

    # Check year if available
    if movie["release_date"]:
        year = movie["release_date"].year
        if str(year) not in release.title:
            return False

    # Get quality profile
    if not movie["media_profile_id"]:
        return False

    profile_row = await conn.fetchrow(
        "SELECT * FROM quality_profiles WHERE id = $1",
        movie["media_profile_id"]
    )

    if not profile_row:
        return False

    profile = MediaProfile(**dict(profile_row))

    # Score the release
    score = media_profile_service.score_release(release, profile)

    if score < 0:
        return False  # Release doesn't meet requirements

    # Add to download client
    try:
        if release.magnet:
            torrent_hash = await qbittorrent_client.add_torrent(
                torrent=release.magnet,
                category="movies",
                tags=["nexarr", f"movie-{movie['id']}"],
            )

            # Record in download history
            await conn.execute(
                """
                INSERT INTO download_history (
                    media_id, media_type, torrent_hash, torrent_title,
                    indexer, quality, size, status, download_client
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                movie["id"], "movie", torrent_hash, release.title,
                release.indexer, release.quality, release.size,
                "downloading", "qbittorrent"
            )

            # Update movie status
            await conn.execute(
                "UPDATE movies SET status = 'downloading', updated_at = NOW() WHERE id = $1",
                movie["id"]
            )

            return True

    except Exception as e:
        print(f"Error grabbing release: {e}")

    return False


async def check_and_grab_show(conn, release, show):
    """
    Check if release matches wanted show episode and grab it
    """
    import re

    release_title_lower = release.title.lower()
    show_title_lower = show["title"].lower()

    if show_title_lower not in release_title_lower:
        return False

    # Parse season and episode from release title (supports S##E##, ##x##, etc.)
    season_episode_patterns = [
        r's(\d{1,2})e(\d{1,2})',  # S01E01
        r'(\d{1,2})x(\d{1,2})',    # 1x01
        r'season\s*(\d{1,2})\s*episode\s*(\d{1,2})',  # Season 1 Episode 01
    ]

    matched_season = None
    matched_episode = None

    for pattern in season_episode_patterns:
        match = re.search(pattern, release_title_lower)
        if match:
            matched_season = int(match.group(1))
            matched_episode = int(match.group(2))
            break

    if not matched_season or not matched_episode:
        return False

    # Get quality profile
    if not show["media_profile_id"]:
        return False

    profile_row = await conn.fetchrow(
        "SELECT * FROM quality_profiles WHERE id = $1",
        show["media_profile_id"]
    )

    if not profile_row:
        return False

    profile = MediaProfile(**dict(profile_row))

    # Score the release
    score = media_profile_service.score_release(release, profile)

    if score < 0:
        return False

    # Add to download client
    try:
        if release.magnet:
            torrent_hash = await qbittorrent_client.add_torrent(
                torrent=release.magnet,
                category="tv",
                tags=["nexarr", f"show-{show['id']}", f"s{matched_season:02d}e{matched_episode:02d}"],
            )

            # Record in download history
            await conn.execute(
                """
                INSERT INTO download_history (
                    media_id, media_type, torrent_hash, torrent_title,
                    indexer, quality, size, status, download_client
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                show["id"],
                "show",
                torrent_hash,
                release.title,
                release.indexer if hasattr(release, 'indexer') else 'unknown',
                release.quality,
                release.size,
                "downloading",
                "qbittorrent",
            )

            # Update show status
            await conn.execute(
                """
                UPDATE shows
                SET status = 'downloading', updated_at = NOW()
                WHERE id = $1
                """,
                show["id"],
            )

            # Send notification via WebTransport
            await webtransport_manager.send_notification(
                1,  # TODO: Get actual user_id from show
                "new_download",
                {
                    "title": f"Downloading {show['title']} S{matched_season:02d}E{matched_episode:02d}",
                    "message": release.title,
                    "media_type": "show",
                    "media_id": show["id"],
                },
            )

            return True

    except Exception as e:
        print(f"Error grabbing show release: {e}")
        return False

    return False
