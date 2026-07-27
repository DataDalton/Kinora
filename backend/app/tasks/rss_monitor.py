import re
import time
from datetime import datetime
from app.tasks.celery_app import celery_app, runAsync
from app.db import get_pool
from app.services.automation.search_engine import search_engine, _resolve_grab_folder
from app.services.media_profile import MediaProfile, media_profile_service
from app.services import music_quality
from app.services.release_index import normalizeTitle
from app.services.download_clients.qbittorrent import get_qbittorrent_client
from app.services.torrent_validator import validate_and_resume_torrent
from app.core.webtransport import webtransport_manager
from app.services.notifications import create_notification, SEVERITY_INFO
from app.core.cache import cacheSet


@celery_app.task(name="app.tasks.rss_monitor.monitor_rss_feeds")
def monitor_rss_feeds():
    """
    Monitor new-upload feeds from all enabled indexers.
    Checks for new releases and auto-downloads matches for wanted media across
    movies, shows, anime, and music.
    """
    return runAsync(async_monitor_rss_feeds())


def _title_matches(release_title: str, media_title: str) -> bool:
    """
    Whether a media title appears in a release title, compared on normalized forms
    so punctuation and separator differences (dots, dashes, brackets) never block a
    match. Word-padded containment prevents partial-word hits.
    """
    normalized_media = normalizeTitle(media_title)
    if not normalized_media:
        return False
    return f" {normalized_media} " in f" {normalizeTitle(release_title)} "


def _parse_season_episode(release_title: str):
    """
    Parse season and episode numbers from a release title. Supports S01E01, 1x01,
    "Season 1 Episode 1", and the anime "Title - 05" style (assumed season 1).
    Returns (season, episode) or (None, None).
    """
    title_lower = release_title.lower()

    for pattern in (
        r"s(\d{1,2})e(\d{1,3})",
        r"(\d{1,2})x(\d{1,3})",
        r"season\s*(\d{1,2})\s*episode\s*(\d{1,3})",
    ):
        match = re.search(pattern, title_lower)
        if match:
            return int(match.group(1)), int(match.group(2))

    anime_match = re.search(r"[-_\s](\d{2,3})(?:v\d)?[\s\[\.]", release_title)
    if anime_match:
        return 1, int(anime_match.group(1))

    return None, None


async def _add_release_for_media(
    conn,
    release,
    media_type: str,
    media_id: int,
    profile,
    torrent_category: str,
    extra_tags,
):
    """
    Shared download path for a matched release: resolve the source, add it paused
    to qBittorrent with the paired root folder, record download history, and start
    validation. Returns the torrent hash or None.
    """
    # Resolve the magnet on demand (deferred during the feed scan for speed).
    await search_engine.resolve_download_source(release)
    if not (release.magnet or release.torrent_url):
        return None

    client = await get_qbittorrent_client()
    if not client:
        return None

    # Paired root folder: hardlink download path plus organize target.
    folder = await _resolve_grab_folder(conn, media_type, media_id)
    save_path = folder["download_path"] if folder else None
    root_folder_id = folder["id"] if folder else None

    torrent_hash = await client.add_torrent(
        torrent=release.magnet or release.torrent_url,
        save_path=save_path,
        category=torrent_category,
        tags=["kinora", "validating"] + list(extra_tags),
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
        media_id,
        media_type,
        torrent_hash,
        release.title,
        release.indexer or "unknown",
        release.quality,
        release.size,
        release.magnet,
        release.torrent_url,
        release.info_hash or torrent_hash,
        "downloading",
        root_folder_id,
        "qbittorrent",
    )

    await validate_and_resume_torrent(
        torrent_hash=torrent_hash,
        client=client,
        profile=profile,
        media_type=media_type,
    )

    return torrent_hash


async def async_monitor_rss_feeds():
    """
    Async implementation of new-upload monitoring.
    """
    taskName = "rss_monitor"
    startTime = time.time()
    status = "success"

    try:
        # Get recent releases from all indexer feeds (also persisted into the
        # local release index inside the engine).
        releases = await search_engine.get_rss_updates()

        if not releases:
            return {"status": "success", "releases_found": 0, "grabbed": 0}

        grabbed_count = 0
        pool = await get_pool()

        async with pool.acquire() as conn:
            # All monitored media that have an assigned profile, per type.
            monitoredMovies = await conn.fetch("""
                SELECT m.* FROM movies m
                INNER JOIN media_profiles mp ON m.media_profile_id = mp.id
                WHERE m.monitored = TRUE AND m.has_file = FALSE
                """)

            monitoredShows = await conn.fetch("""
                SELECT s.* FROM shows s
                INNER JOIN media_profiles mp ON s.media_profile_id = mp.id
                WHERE s.monitored = TRUE
                """)

            monitoredAnime = await conn.fetch("""
                SELECT a.* FROM anime a
                INNER JOIN media_profiles mp ON a.media_profile_id = mp.id
                WHERE a.monitored = TRUE
                """)

            wantedAlbums = await conn.fetch("""
                SELECT al.* FROM albums al
                INNER JOIN media_profiles mp ON al.media_profile_id = mp.id
                WHERE al.monitored = TRUE AND al.status = 'wanted'
                """)

            # Batch-load the referenced profiles once, then look them up per item.
            profileIds = list(
                {m["media_profile_id"] for m in monitoredMovies}
                | {s["media_profile_id"] for s in monitoredShows}
                | {a["media_profile_id"] for a in monitoredAnime}
                | {al["media_profile_id"] for al in wantedAlbums}
            )
            profiles = {}
            if profileIds:
                profileRows = await conn.fetch("SELECT * FROM media_profiles WHERE id = ANY($1)", profileIds)
                profiles = {r["id"]: MediaProfile.from_row(dict(r)) for r in profileRows}

            # Items already matched this cycle, so one run never downloads the same
            # item twice from two feed entries.
            downloadedIds = {"movie": set(), "show": set(), "anime": set(), "album": set()}

            for release in releases:
                matched = False

                for movieRow in monitoredMovies:
                    if movieRow["id"] in downloadedIds["movie"]:
                        continue
                    movieDict = dict(movieRow)
                    profile = profiles.get(movieDict["media_profile_id"])
                    if await check_and_grab_movie(conn, release, movieDict, profile):
                        grabbed_count += 1
                        downloadedIds["movie"].add(movieRow["id"])
                        matched = True
                        break
                if matched:
                    continue

                for showRow in monitoredShows:
                    showDict = dict(showRow)
                    profile = profiles.get(showDict["media_profile_id"])
                    if await check_and_grab_show(conn, release, showDict, profile):
                        grabbed_count += 1
                        matched = True
                        break
                if matched:
                    continue

                for animeRow in monitoredAnime:
                    animeDict = dict(animeRow)
                    profile = profiles.get(animeDict["media_profile_id"])
                    if await check_and_download_anime(conn, release, animeDict, profile):
                        grabbed_count += 1
                        matched = True
                        break
                if matched:
                    continue

                for albumRow in wantedAlbums:
                    if albumRow["id"] in downloadedIds["album"]:
                        continue
                    albumDict = dict(albumRow)
                    profile = profiles.get(albumDict["media_profile_id"])
                    if await check_and_download_album(conn, release, albumDict, profile):
                        grabbed_count += 1
                        downloadedIds["album"].add(albumRow["id"])
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
    Check if a release matches a wanted movie and download it.
    profile is the resolved MediaProfile for the movie's media_profile_id.
    """
    if not profile:
        return False

    if not _title_matches(release.title, movie["title"]):
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

    try:
        torrent_hash = await _add_release_for_media(
            conn,
            release,
            "movie",
            movie["id"],
            profile,
            torrent_category="movies",
            extra_tags=[f"movie-{movie['id']}"],
        )
        if not torrent_hash:
            return False

        await conn.execute("UPDATE movies SET status = 'downloading', updated_at = NOW() WHERE id = $1", movie["id"])

        await create_notification(
            type="new_download",
            title=f"Downloading {movie['title']}",
            message=release.title,
            severity=SEVERITY_INFO,
            data={"media_type": "movie", "media_id": movie["id"]},
        )

        return True

    except Exception as e:
        print(f"Error downloading movie release: {e}")

    return False


async def check_and_grab_show(conn, release, show, profile):
    """
    Check if a release matches a wanted show episode and download it.
    profile is the resolved MediaProfile for the show's media_profile_id.
    """
    if not profile:
        return False

    if not _title_matches(release.title, show["title"]):
        return False

    matchedSeason, matchedEpisode = _parse_season_episode(release.title)
    if not matchedSeason or not matchedEpisode:
        return False

    # Score the release with show-specific settings
    score = media_profile_service.score_release(release, profile, media_type="show")

    if score < 0:
        return False

    try:
        torrentHash = await _add_release_for_media(
            conn,
            release,
            "show",
            show["id"],
            profile,
            torrent_category="tv",
            extra_tags=[f"show-{show['id']}", f"s{matchedSeason:02d}e{matchedEpisode:02d}"],
        )
        if not torrentHash:
            return False

        await conn.execute(
            "UPDATE shows SET status = 'downloading', updated_at = NOW() WHERE id = $1",
            show["id"],
        )

        await create_notification(
            type="new_download",
            title=f"Downloading {show['title']} S{matchedSeason:02d}E{matchedEpisode:02d}",
            message=release.title,
            severity=SEVERITY_INFO,
            data={"media_type": "show", "media_id": show["id"]},
        )

        return True

    except Exception as e:
        print(f"Error downloading show release: {e}")
        return False


async def check_and_download_anime(conn, release, anime, profile):
    """
    Check if a release matches a monitored anime episode and download it.
    profile is the resolved MediaProfile for the anime's media_profile_id.
    """
    if not profile:
        return False

    if not _title_matches(release.title, anime["title"]):
        return False

    matchedSeason, matchedEpisode = _parse_season_episode(release.title)
    if not matchedEpisode:
        return False

    # Score with anime-specific settings, including the subtitle/audio raw data
    # Nyaa parsing provides.
    score = media_profile_service.score_release(release, profile, media_type="anime")

    if score < 0:
        return False

    try:
        torrentHash = await _add_release_for_media(
            conn,
            release,
            "anime",
            anime["id"],
            profile,
            torrent_category="anime",
            extra_tags=[f"anime-{anime['id']}", f"e{matchedEpisode:03d}"],
        )
        if not torrentHash:
            return False

        await conn.execute(
            "UPDATE anime SET status = 'downloading', updated_at = NOW() WHERE id = $1",
            anime["id"],
        )

        await create_notification(
            type="new_download",
            title=f"Downloading {anime['title']} episode {matchedEpisode}",
            message=release.title,
            severity=SEVERITY_INFO,
            data={"media_type": "anime", "media_id": anime["id"]},
        )

        return True

    except Exception as e:
        print(f"Error downloading anime release: {e}")
        return False


async def check_and_download_album(conn, release, album, profile):
    """
    Check if a release matches a wanted album and download it.
    Requires both the artist name and album title in the release title, and the
    release's parsed quality tier to be allowed by the profile.
    """
    if not profile:
        return False

    artistName = album.get("artist_name") or ""
    if not _title_matches(release.title, album["title"]):
        return False
    if artistName and not _title_matches(release.title, artistName):
        return False

    # Tier gate: an identifiable tier must be allowed by the profile. Unknown tiers
    # pass so a mislabeled release is not dropped, mirroring the search engine.
    allowed = getattr(profile, "music_quality_tiers", None) or music_quality.DEFAULT_TIERS
    tier = getattr(release, "quality_tier", None) or music_quality.tier_from_release(release)
    if tier is not None and tier not in allowed:
        return False

    try:
        torrentHash = await _add_release_for_media(
            conn,
            release,
            "album",
            album["id"],
            profile,
            torrent_category="music",
            extra_tags=["music", f"album-{album['id']}"],
        )
        if not torrentHash:
            return False

        await conn.execute(
            "UPDATE albums SET status = 'downloading', updated_at = NOW() WHERE id = $1",
            album["id"],
        )

        await create_notification(
            type="new_download",
            title=f"Downloading {album['title']}" + (f" by {artistName}" if artistName else ""),
            message=release.title,
            severity=SEVERITY_INFO,
            data={"media_type": "album", "media_id": album["id"]},
        )

        return True

    except Exception as e:
        print(f"Error downloading album release: {e}")
        return False
