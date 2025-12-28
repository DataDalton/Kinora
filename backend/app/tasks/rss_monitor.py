import time
from datetime import datetime
from app.tasks.celery_app import celery_app, runAsync
from app.db import get_pool
from app.services.automation.search_engine import search_engine
from app.services.media_profile import MediaProfile, media_profile_service
from app.services.download_clients.qbittorrent import get_qbittorrent_client
from app.services.torrent_validator import validate_and_resume_torrent
from app.core.webtransport import webtransport_manager
from app.core.cache import cacheSet


@celery_app.task(name="app.tasks.rss_monitor.monitor_rss_feeds")
def monitor_rss_feeds():
    """
    Monitor RSS feeds from all enabled indexers
    Checks for new releases and auto-grabs matching wanted media
    """
    return runAsync(async_monitor_rss_feeds())


async def async_monitor_rss_feeds():
    """
    Async implementation of RSS monitoring
    """
    taskName = "rss_monitor"
    startTime = time.time()
    status = "success"

    try:
        # Get recent releases from all indexers
        releases = await search_engine.get_rss_updates()

        if not releases:
            return {"status": "success", "releases_found": 0, "grabbed": 0}

        grabbed_count = 0
        pool = await get_pool()

        async with pool.acquire() as conn:
            # Get all monitored media with their profiles using JOIN
            monitoredMoviesWithProfiles = await conn.fetch(
                """
                SELECT m.*, mp.id as mp_id, mp.name as mp_name, mp.resolutions,
                       mp.sources, mp.codecs, mp.uploaders, mp.min_seeds,
                       mp.min_size, mp.max_size, mp.search_timeout, mp.max_results
                FROM movies m
                INNER JOIN media_profiles mp ON m.media_profile_id = mp.id
                WHERE m.monitored = TRUE AND m.has_file = FALSE
                """
            )

            monitoredShowsWithProfiles = await conn.fetch(
                """
                SELECT s.*, mp.id as mp_id, mp.name as mp_name, mp.resolutions,
                       mp.sources, mp.codecs, mp.uploaders, mp.min_seeds,
                       mp.min_size, mp.max_size, mp.search_timeout, mp.max_results
                FROM shows s
                INNER JOIN media_profiles mp ON s.media_profile_id = mp.id
                WHERE s.monitored = TRUE
                """
            )

            # Check each release against wanted media
            for release in releases:
                # Try to match against movies
                for movieRow in monitoredMoviesWithProfiles:
                    movieDict = dict(movieRow)
                    if await check_and_grab_movie(conn, release, movieDict):
                        grabbed_count += 1
                        break

                # Try to match against shows
                for showRow in monitoredShowsWithProfiles:
                    showDict = dict(showRow)
                    if await check_and_grab_show(conn, release, showDict):
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
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    except Exception as e:
        status = "failed"
        print(f"RSS monitoring error: {e}")
        return {"status": "error", "message": str(e)}

    finally:
        elapsedMs = int((time.time() - startTime) * 1000)
        await cacheSet(f"task:last_run:{taskName}", {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "status": status,
            "durationMs": elapsedMs,
        }, expire=86400)


async def check_and_grab_movie(conn, release, movie):
    """
    Check if release matches wanted movie and grab it.
    Movie dict includes pre-joined profile fields (mp_id, mp_name, etc.)
    """
    # Simple title matching (can be enhanced with fuzzy matching)
    releaseTitleLower = release.title.lower()
    movieTitleLower = movie["title"].lower()

    if movieTitleLower not in releaseTitleLower:
        return False

    # Check year if available
    if movie["release_date"]:
        year = movie["release_date"].year
        if str(year) not in release.title:
            return False

    # Check for pre-joined profile data
    if not movie.get("mp_id"):
        return False

    # Construct MediaProfile from pre-joined columns
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

    # Score the release with movie-specific settings
    score = media_profile_service.score_release(release, profile, media_type='movie')

    if score < 0:
        return False  # Release doesn't meet requirements

    # Add to download client
    try:
        if release.magnet:
            client = await get_qbittorrent_client()
            if not client:
                return False

            # Add torrent paused with validating tag for pre-download validation
            torrent_hash = await client.add_torrent(
                torrent=release.magnet,
                category="movies",
                tags=["nexarr", "validating", f"movie-{movie['id']}"],
                paused=True,
            )

            # Trigger validation immediately after adding
            await validate_and_resume_torrent(
                torrent_hash=torrent_hash,
                client=client,
                profile=profile,
                media_type="movie",
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
    Check if release matches wanted show episode and grab it.
    Show dict includes pre-joined profile fields (mp_id, mp_name, etc.)
    """
    import re

    releaseTitleLower = release.title.lower()
    showTitleLower = show["title"].lower()

    if showTitleLower not in releaseTitleLower:
        return False

    # Parse season and episode from release title (supports S##E##, ##x##, etc.)
    seasonEpisodePatterns = [
        r's(\d{1,2})e(\d{1,2})',  # S01E01
        r'(\d{1,2})x(\d{1,2})',    # 1x01
        r'season\s*(\d{1,2})\s*episode\s*(\d{1,2})',  # Season 1 Episode 01
    ]

    matchedSeason = None
    matchedEpisode = None

    for pattern in seasonEpisodePatterns:
        match = re.search(pattern, releaseTitleLower)
        if match:
            matchedSeason = int(match.group(1))
            matchedEpisode = int(match.group(2))
            break

    if not matchedSeason or not matchedEpisode:
        return False

    # Check for pre-joined profile data
    if not show.get("mp_id"):
        return False

    # Construct MediaProfile from pre-joined columns
    profileData = {
        "id": show["mp_id"],
        "name": show["mp_name"],
        "resolutions": show["resolutions"],
        "sources": show["sources"],
        "codecs": show["codecs"],
        "uploaders": show["uploaders"],
        "min_seeds": show["min_seeds"],
        "min_size": show["min_size"],
        "max_size": show["max_size"],
        "search_timeout": show["search_timeout"],
        "max_results": show["max_results"],
    }
    profile = MediaProfile(**profileData)

    # Score the release with show-specific settings
    score = media_profile_service.score_release(release, profile, media_type='show')

    if score < 0:
        return False

    # Add to download client
    try:
        if release.magnet:
            client = await get_qbittorrent_client()
            if not client:
                return False

            # Add torrent paused with validating tag for pre-download validation
            torrentHash = await client.add_torrent(
                torrent=release.magnet,
                category="tv",
                tags=["nexarr", "validating", f"show-{show['id']}", f"s{matchedSeason:02d}e{matchedEpisode:02d}"],
                paused=True,
            )

            # Trigger validation immediately after adding
            await validate_and_resume_torrent(
                torrent_hash=torrentHash,
                client=client,
                profile=profile,
                media_type="show",
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
                torrentHash,
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
                    "title": f"Downloading {show['title']} S{matchedSeason:02d}E{matchedEpisode:02d}",
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
