import time
from datetime import datetime
from app.tasks.celery_app import celery_app, runAsync
from app.db import get_pool
from app.services.automation.search_engine import search_engine, _resolve_grab_folder
from app.services.media_profile import MediaProfile, media_profile_service
from app.services.download_clients.qbittorrent import get_qbittorrent_client
from app.services.torrent_validator import validate_and_resume_torrent
from app.core.webtransport import webtransport_manager
from app.services.notifications import create_notification, SEVERITY_INFO
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
            # Get all monitored media that have an assigned profile
            monitoredMoviesWithProfiles = await conn.fetch("""
                SELECT m.*
                FROM movies m
                INNER JOIN media_profiles mp ON m.media_profile_id = mp.id
                WHERE m.monitored = TRUE AND m.has_file = FALSE
                """)

            monitoredShowsWithProfiles = await conn.fetch("""
                SELECT s.*
                FROM shows s
                INNER JOIN media_profiles mp ON s.media_profile_id = mp.id
                WHERE s.monitored = TRUE
                """)

            # Batch-load the referenced profiles once, then look them up per item.
            profileIds = list(
                {m["media_profile_id"] for m in monitoredMoviesWithProfiles}
                | {s["media_profile_id"] for s in monitoredShowsWithProfiles}
            )
            profiles = {}
            if profileIds:
                profileRows = await conn.fetch("SELECT * FROM media_profiles WHERE id = ANY($1)", profileIds)
                profiles = {r["id"]: MediaProfile.from_row(dict(r)) for r in profileRows}

            # Check each release against wanted media
            for release in releases:
                # Try to match against movies
                for movieRow in monitoredMoviesWithProfiles:
                    movieDict = dict(movieRow)
                    profile = profiles.get(movieDict["media_profile_id"])
                    if await check_and_grab_movie(conn, release, movieDict, profile):
                        grabbed_count += 1
                        break

                # Try to match against shows
                for showRow in monitoredShowsWithProfiles:
                    showDict = dict(showRow)
                    profile = profiles.get(showDict["media_profile_id"])
                    if await check_and_grab_show(conn, release, showDict, profile):
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
        await cacheSet(
            f"task:last_run:{taskName}",
            {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "status": status,
                "durationMs": elapsedMs,
            },
            expire=86400,
        )


async def check_and_grab_movie(conn, release, movie, profile):
    """
    Check if release matches wanted movie and grab it.
    profile is the resolved MediaProfile for the movie's media_profile_id.
    """
    if not profile:
        return False

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

    # Score the release with movie-specific settings
    score = media_profile_service.score_release(release, profile, media_type="movie")

    if score < 0:
        return False  # Release doesn't meet requirements

    # Add to download client
    try:
        # Resolve the magnet on demand (deferred during the RSS scan for speed).
        await search_engine.resolve_download_source(release)
        if release.magnet or release.torrent_url:
            client = await get_qbittorrent_client()
            if not client:
                return False

            # Resolve the paired root folder so the torrent lands in the hardlink folder and
            # the organizer knows where to place it on completion.
            folder = await _resolve_grab_folder(conn, "movie", movie["id"])
            savePath = folder["download_path"] if folder else None
            rootFolderId = folder["id"] if folder else None

            # Add torrent paused with validating tag for pre-download validation
            torrent_hash = await client.add_torrent(
                torrent=release.magnet or release.torrent_url,
                save_path=savePath,
                category="movies",
                tags=["kinora", "validating", f"movie-{movie['id']}"],
                paused=True,
            )

            # Record in download history before validation so the row exists for it.
            await conn.execute(
                """
                INSERT INTO download_history (
                    media_id, media_type, torrent_hash, torrent_title,
                    indexer, quality, size, magnet_link, torrent_url, info_hash,
                    status, root_folder_id, download_client
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                ON CONFLICT (torrent_hash) DO UPDATE SET
                    magnet_link = COALESCE(EXCLUDED.magnet_link, download_history.magnet_link),
                    torrent_url = COALESCE(EXCLUDED.torrent_url, download_history.torrent_url),
                    info_hash = COALESCE(EXCLUDED.info_hash, download_history.info_hash),
                    root_folder_id = COALESCE(EXCLUDED.root_folder_id, download_history.root_folder_id),
                    updated_at = NOW()
                """,
                movie["id"],
                "movie",
                torrent_hash,
                release.title,
                release.indexer,
                release.quality,
                release.size,
                release.magnet,
                release.torrent_url,
                release.info_hash or torrent_hash,
                "downloading",
                rootFolderId,
                "qbittorrent",
            )

            # Trigger validation immediately after adding
            await validate_and_resume_torrent(
                torrent_hash=torrent_hash,
                client=client,
                profile=profile,
                media_type="movie",
            )

            # Update movie status
            await conn.execute(
                "UPDATE movies SET status = 'downloading', updated_at = NOW() WHERE id = $1", movie["id"]
            )

            return True

    except Exception as e:
        print(f"Error grabbing release: {e}")

    return False


async def check_and_grab_show(conn, release, show, profile):
    """
    Check if release matches wanted show episode and grab it.
    profile is the resolved MediaProfile for the show's media_profile_id.
    """
    import re

    if not profile:
        return False

    releaseTitleLower = release.title.lower()
    showTitleLower = show["title"].lower()

    if showTitleLower not in releaseTitleLower:
        return False

    # Parse season and episode from release title (supports S##E##, ##x##, etc.)
    seasonEpisodePatterns = [
        r"s(\d{1,2})e(\d{1,2})",  # S01E01
        r"(\d{1,2})x(\d{1,2})",  # 1x01
        r"season\s*(\d{1,2})\s*episode\s*(\d{1,2})",  # Season 1 Episode 01
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

    # Score the release with show-specific settings
    score = media_profile_service.score_release(release, profile, media_type="show")

    if score < 0:
        return False

    # Add to download client
    try:
        # Resolve the magnet on demand (deferred during the RSS scan for speed).
        await search_engine.resolve_download_source(release)
        if release.magnet or release.torrent_url:
            client = await get_qbittorrent_client()
            if not client:
                return False

            # Resolve the paired root folder (hardlink folder + organize target).
            folder = await _resolve_grab_folder(conn, "show", show["id"])
            savePath = folder["download_path"] if folder else None
            rootFolderId = folder["id"] if folder else None

            # Add torrent paused with validating tag for pre-download validation
            torrentHash = await client.add_torrent(
                torrent=release.magnet or release.torrent_url,
                save_path=savePath,
                category="tv",
                tags=["kinora", "validating", f"show-{show['id']}", f"s{matchedSeason:02d}e{matchedEpisode:02d}"],
                paused=True,
            )

            # Record in download history before validation so the row exists for it.
            await conn.execute(
                """
                INSERT INTO download_history (
                    media_id, media_type, torrent_hash, torrent_title,
                    indexer, quality, size, magnet_link, torrent_url, info_hash,
                    status, root_folder_id, download_client
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                ON CONFLICT (torrent_hash) DO UPDATE SET
                    magnet_link = COALESCE(EXCLUDED.magnet_link, download_history.magnet_link),
                    torrent_url = COALESCE(EXCLUDED.torrent_url, download_history.torrent_url),
                    info_hash = COALESCE(EXCLUDED.info_hash, download_history.info_hash),
                    root_folder_id = COALESCE(EXCLUDED.root_folder_id, download_history.root_folder_id),
                    updated_at = NOW()
                """,
                show["id"],
                "show",
                torrentHash,
                release.title,
                release.indexer if hasattr(release, "indexer") else "unknown",
                release.quality,
                release.size,
                release.magnet,
                release.torrent_url,
                release.info_hash or torrentHash,
                "downloading",
                rootFolderId,
                "qbittorrent",
            )

            # Trigger validation immediately after adding
            await validate_and_resume_torrent(
                torrent_hash=torrentHash,
                client=client,
                profile=profile,
                media_type="show",
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

            # Persist an in-app notification and push it to all connected clients.
            await create_notification(
                type="new_download",
                title=f"Downloading {show['title']} S{matchedSeason:02d}E{matchedEpisode:02d}",
                message=release.title,
                severity=SEVERITY_INFO,
                data={"media_type": "show", "media_id": show["id"]},
            )

            return True

    except Exception as e:
        print(f"Error grabbing show release: {e}")
        return False

    return False
