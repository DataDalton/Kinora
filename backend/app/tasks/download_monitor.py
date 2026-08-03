import os
import re
import time
import shutil
import asyncio
from pathlib import Path
from datetime import datetime
from app.tasks.celery_app import celery_app, runAsync
from app.db import get_pool
from app.services.download_clients.qbittorrent import get_qbittorrent_client
from app.services.download_clients.base import TorrentState
from app.core.webtransport import webtransport_manager
from app.services.file_manager import FileManager
from app.services.metadata_extractor import MetadataExtractor
from app.services.folder_selector import folderSelector
from app.services import naming_tokens
from app.services import artwork
from app.services import nfo
from app.services import music_tagging
from app.services import music_quality
from app.services import media_files
from app.core.cache import cacheSet

# Mark a download's history row completed. Used both for the terminal "media item is
# gone" case and inside the short completion transaction.
_MARK_DOWNLOAD_COMPLETED = """
    UPDATE download_history
    SET status = 'completed', completed_at = NOW(), progress = 1.0, updated_at = NOW()
    WHERE torrent_hash = $1
"""


async def get_file_operation(conn, media_id: int, media_type: str) -> str:
    """
    Get file operation (hardlink/copy) from media's profile.
    Returns 'hardlink' if use_hardlinks is True, 'copy' otherwise.
    Defaults to 'hardlink' if no profile is set.
    """
    table_map = {
        "movie": "movies",
        "show": "shows",
        "anime": "anime",
        "album": "albums",
    }

    table = table_map.get(media_type)
    if not table:
        return "hardlink"

    result = await conn.fetchrow(
        f"""
        SELECT mp.use_hardlinks
        FROM {table} m
        LEFT JOIN media_profiles mp ON m.media_profile_id = mp.id
        WHERE m.id = $1
        """,
        media_id,
    )

    if result and result["use_hardlinks"] is not None:
        return "hardlink" if result["use_hardlinks"] else "copy"

    return "hardlink"


async def get_profile_settings(conn, media_id: int, media_type: str) -> dict:
    """
    Get profile settings for file organization.
    Returns dict with naming formats and character replacement settings.
    """
    table_map = {
        "movie": "movies",
        "show": "shows",
        "anime": "anime",
        "album": "albums",
    }

    table = table_map.get(media_type)
    if not table:
        return {}

    result = await conn.fetchrow(
        f"""
        SELECT
            mp.use_hardlinks,
            mp.media_server,
            mp.upgrade_replace_policy,
            mp.illegal_char_replacement,
            mp.colon_replacement,
            mp.movie_naming_format,
            mp.movie_folder_format,
            mp.show_naming_format,
            mp.show_folder_format,
            mp.anime_naming_format,
            mp.anime_folder_format,
            mp.music_artist_folder_format,
            mp.music_album_folder_format,
            mp.music_track_naming_format,
            mp.music_multi_disc_format,
            mp.music_embed_lyrics,
            mp.music_embed_artwork
        FROM {table} m
        LEFT JOIN media_profiles mp ON m.media_profile_id = mp.id
        WHERE m.id = $1
        """,
        media_id,
    )

    if not result:
        return {}

    return dict(result)


def organize_file_hardlink(file_manager: FileManager, source: str, dest: str) -> bool:
    """
    Organize file using hardlink only. No fallback to copy.
    Root folder and download folder are paired on same filesystem to guarantee hardlinks work.
    Returns True on success, raises exception on failure.
    """
    return file_manager.organize_file(source, dest, "hardlink")


def parse_episode_info(filename: str) -> dict:
    """
    Parse season and episode numbers from filename.
    Returns dict with season_number, episode_number, and episode_title (if found).
    """
    result = {
        "season_number": None,
        "episode_number": None,
        "episode_title": None,
    }

    # Standard patterns: S01E01, S1E1, 1x01
    patterns = [
        r"[Ss](\d{1,2})[Ee](\d{1,3})",  # S01E01
        r"(\d{1,2})x(\d{1,3})",  # 1x01
        r"[Ss]eason\s*(\d{1,2}).*[Ee]pisode\s*(\d{1,3})",  # Season 1 Episode 1
    ]

    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            result["season_number"] = int(match.group(1))
            result["episode_number"] = int(match.group(2))
            break

    # Anime-style: [Group] Title - 01 [Quality].mkv
    if result["episode_number"] is None:
        anime_pattern = r"[-_\s](\d{2,3})(?:v\d)?[\s\[\.]"
        match = re.search(anime_pattern, filename)
        if match:
            result["episode_number"] = int(match.group(1))
            result["season_number"] = 1  # Assume season 1 for anime

    return result


@celery_app.task(name="app.tasks.download_monitor.check_downloads")
def check_downloads():
    """
    Monitor download client for active downloads
    Updates progress and triggers post-processing when complete
    """
    return runAsync(async_check_downloads())


async def async_check_downloads():
    """
    Async implementation of download monitoring
    """
    taskName = "download_monitor"
    startTime = time.time()
    status = "success"

    try:
        # Get qBittorrent client instance
        client = await get_qbittorrent_client()
        if not client:
            return {"status": "skipped", "reason": "qBittorrent not configured"}

        # One client-wide listing feeds the global transfer-stats sample (bandwidth and
        # ratio charts need every torrent for accurate totals).
        allTorrents = await client.get_torrents()

        from app.services.transfer_stats import record_transfer_sample

        await record_transfer_sample(client, allTorrents)

        pool = await get_pool()
        to_process = []  # torrent hashes to hand off to the per-download import task

        async with pool.acquire() as conn:
            # Only the lightweight tracking columns are needed here. The heavy per-file
            # import runs in a separate task that re-reads the full row, so the poll never
            # organizes inline or holds a connection across file I/O.
            activeRows = await conn.fetch(
                "SELECT torrent_hash, status FROM download_history "
                "WHERE status IN ('downloading', 'pending', 'processing')"
            )
            if not activeRows:
                return {"status": "success", "active_downloads": 0, "dispatched": 0}

            statusByHash = {r["torrent_hash"]: r["status"] for r in activeRows}
            ourTorrents = [t for t in allTorrents if t.hash in statusByHash]
            user_ids = webtransport_manager.get_active_users()

            progress_hashes = []
            progress_values = []
            newly_completed = []
            errored = []

            for torrent in ourTorrents:
                is_active = statusByHash[torrent.hash] in ("downloading", "pending")

                if is_active:
                    progress_hashes.append(torrent.hash)
                    progress_values.append(float(torrent.progress))
                    # Push a progress update only while actively downloading. Seeding or
                    # completed torrents carry no useful delta and would spam every client.
                    if torrent.state == TorrentState.DOWNLOADING:
                        for user_id in user_ids:
                            await webtransport_manager.send_download_update(
                                user_id, torrent.hash, torrent.progress, torrent.download_speed
                            )

                    if torrent.state == TorrentState.SEEDING or torrent.progress >= 1.0:
                        newly_completed.append(torrent.hash)
                    elif torrent.state == TorrentState.ERROR:
                        errored.append(torrent.hash)

            # One round-trip for every progress update instead of one per torrent.
            if progress_hashes:
                await conn.execute(
                    """
                    UPDATE download_history AS dh
                    SET progress = d.progress, updated_at = NOW()
                    FROM (SELECT unnest($1::text[]) AS hash, unnest($2::float8[]) AS progress) AS d
                    WHERE dh.torrent_hash = d.hash AND dh.status IN ('downloading', 'pending')
                    """,
                    progress_hashes,
                    progress_values,
                )

            # Atomically claim completed downloads for import in one round-trip. RETURNING
            # yields only the rows this poll transitioned, so an overlapping poll that
            # loses the race dispatches nothing and the same download is never imported twice.
            if newly_completed:
                claimed = await conn.fetch(
                    "UPDATE download_history SET status = 'processing', updated_at = NOW() "
                    "WHERE torrent_hash = ANY($1) AND status IN ('downloading', 'pending') "
                    "RETURNING torrent_hash",
                    newly_completed,
                )
                to_process.extend(r["torrent_hash"] for r in claimed)

            if errored:
                await conn.execute(
                    "UPDATE download_history SET status = 'failed', "
                    "error_message = 'Torrent error in download client', updated_at = NOW() "
                    "WHERE torrent_hash = ANY($1) AND status IN ('downloading', 'pending')",
                    errored,
                )

            # Recover downloads stuck in 'processing' (a worker died mid-import). Claiming
            # by bumping updated_at (RETURNING the claimed rows) both makes the recovery
            # race-safe and backs off the next retry by another window. The threshold sits
            # above the task time limit so an in-progress import is never re-dispatched.
            our_hashes = [t.hash for t in ourTorrents]
            if our_hashes:
                stale = await conn.fetch(
                    "UPDATE download_history SET updated_at = NOW() "
                    "WHERE status = 'processing' AND torrent_hash = ANY($1) "
                    "AND updated_at < NOW() - INTERVAL '35 minutes' "
                    "RETURNING torrent_hash",
                    our_hashes,
                )
                to_process.extend(r["torrent_hash"] for r in stale)

        # Dispatch after releasing the connection. Each import runs in its own task, in
        # parallel across workers, with its own connection.
        for torrent_hash in to_process:
            process_completed_download.delay(torrent_hash)

        return {
            "status": "success",
            "active_downloads": len(ourTorrents),
            "dispatched": len(to_process),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    except Exception as e:
        status = "failed"
        print(f"Download monitoring error: {e}")
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


@celery_app.task(name="app.tasks.download_monitor.process_completed_download")
def process_completed_download(torrent_hash: str):
    """
    Organize and import one completed download. Dispatched by the poll per download so
    imports run in parallel across workers and never block the poll or hold its connection.
    """
    return runAsync(async_process_completed_download(torrent_hash))


async def async_process_completed_download(torrent_hash: str):
    """Import a single download claimed in the 'processing' state. Idempotent."""
    client = await get_qbittorrent_client()
    if not client:
        return {"status": "skipped", "reason": "qBittorrent not configured"}

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM download_history WHERE torrent_hash = $1", torrent_hash)
        if not row:
            return {"status": "skipped", "reason": "no download record"}
        # Only the row the poll claimed (status 'processing') is imported. A repeat
        # dispatch after completion, or a race with another worker, is a no-op.
        if row["status"] != "processing":
            return {"status": "skipped", "reason": f"status={row['status']}"}
        download_dict = dict(row)

    # The full torrent info (save_path, name) is needed to organize. Fetch by hash so the
    # import does not depend on the poll's torrent snapshot.
    torrent = await client.get_torrent(torrent_hash)
    if not torrent:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE download_history SET status = 'failed', "
                "error_message = 'Torrent no longer in download client', updated_at = NOW() "
                "WHERE torrent_hash = $1",
                torrent_hash,
            )
        return {"status": "failed", "reason": "torrent not found in client"}

    async with pool.acquire() as conn:
        await handle_completed_download(conn, download_dict, torrent)
    return {"status": "ok", "torrent_hash": torrent_hash}


def _unique_destination(path: str) -> str:
    """
    Return a path that does not collide with an existing file, appending a Jellyfin
    version suffix (" - v2", " - v3", ...) before the extension. Used for the
    keep_versions policy so a new version never overwrites an existing one. The suffix
    stays after the folder-name prefix so Jellyfin still reads the files as one item.
    """
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    counter = 2
    while True:
        candidate = f"{base} - v{counter}{ext}"
        if not os.path.exists(candidate):
            return candidate
        counter += 1


def apply_replace_policy(grab_mode, policy, old_file_path, new_file_path):
    """
    Handle the previous file when an upgrade is imported. delete_old removes it (the only
    path that deletes a file, and only because the profile opts in); keep_old and
    keep_versions leave it in place. keep_versions relies on the new file being written
    to a distinct name (see the keep_versions handling in the organize phase), so both
    versions coexist in the item folder.
    """
    if grab_mode != "upgrade" or not old_file_path:
        return
    if os.path.normpath(old_file_path) == os.path.normpath(new_file_path):
        return  # written in place, nothing to clean up
    if policy == "delete_old":
        try:
            if os.path.isfile(old_file_path):
                os.remove(old_file_path)
                print(f"Upgrade: removed replaced file {old_file_path}")
            elif os.path.isdir(old_file_path):
                shutil.rmtree(old_file_path)
                print(f"Upgrade: removed replaced folder {old_file_path}")
        except OSError as e:
            print(f"Could not remove replaced path {old_file_path}: {e}")
    else:
        print(f"Upgrade: kept previous file (policy={policy}): {old_file_path}")


async def handle_completed_download(conn, download_record, torrent):
    """
    Handle post-processing for a completed download.

    All slow work (organizing with hardlinks, ffprobe, tagging, artwork) runs with no
    transaction held. Only the final download-history and media-row writes are wrapped
    in a short transaction, so a connection is never held open across file I/O. If
    organizing raises, the download is never marked completed and is retried next cycle.
    """
    try:
        media_id = download_record["media_id"]
        media_type = download_record["media_type"]
        root_folder_id = download_record.get("root_folder_id")

        root_folder = await folderSelector.getFolder(conn, root_folder_id) if root_folder_id else None
        if not root_folder:
            print(f"No root folder found for download {torrent.hash}")
            return

        root_path = root_folder["root_path"]

        file_manager = FileManager()
        metadata_extractor = MetadataExtractor()

        profile = await get_profile_settings(conn, media_id, media_type)
        illegal_replacement = profile.get("illegal_char_replacement") or ""
        colon_replacement = profile.get("colon_replacement") or " -"

        grab_mode = download_record.get("grab_mode") or "auto"
        replace_policy = profile.get("upgrade_replace_policy") or "keep_old"
        old_file_path = None
        if grab_mode == "upgrade" and media_type in ("movie", "show", "anime", "album"):
            _table = {"movie": "movies", "show": "shows", "anime": "anime", "album": "albums"}[media_type]
            old_file_path = await conn.fetchval(f"SELECT file_path FROM {_table} WHERE id = $1", media_id)
        # When keeping versions, an upgrade must not overwrite the existing file, so each
        # organized path is made unique before linking. Off for other policies so normal
        # names are untouched.
        keep_versions = grab_mode == "upgrade" and replace_policy == "keep_versions"

        # Outputs collected by the organize phase, applied afterward. No transaction is
        # held while these are produced.
        title = "Media"
        media_update = None  # (sql, params) for the media-row update, or None
        media_file_rows = []  # list of (file_path, attrs) to persist into media_files
        subtitle_dispatch = []  # list of (media_type, path) to queue subtitle searches for
        transcode_dispatch = []  # list of (media_type, path) to evaluate transcoding rules against
        replace_new_path = None  # organized path for the upgrade replace policy

        # ---- Organize phase (no transaction) ----
        if media_type == "movie":
            movie = await conn.fetchrow(
                """
                SELECT title, release_date, tmdb_id, imdb_id, poster_path, backdrop_path,
                       overview, genres
                FROM movies WHERE id = $1
                """,
                media_id,
            )
            if not movie:
                print(f"Movie not found: {media_id}")
                await conn.execute(_MARK_DOWNLOAD_COMPLETED, torrent.hash)
                return

            title = movie["title"]
            source_path = file_manager.extract_largest_video(torrent.save_path)

            if not source_path:
                print(f"No video file found in {torrent.save_path}")
                media_update = (
                    "UPDATE movies SET status = 'completed', has_file = TRUE, file_path = $1, "
                    "file_size = $2, root_folder_id = $3, updated_at = NOW() WHERE id = $4",
                    (torrent.save_path, torrent.size, root_folder_id, media_id),
                )
            else:
                file_metadata = await asyncio.to_thread(metadata_extractor.extract_metadata, source_path)
                quality_detected = file_metadata.get("quality") if file_metadata else None

                naming_pattern = profile.get("movie_naming_format") or "{Movie CleanTitle} ({Release Year})"
                folder_pattern = profile.get("movie_folder_format") or "{Movie CleanTitle} ({Release Year})"

                source_ext = Path(source_path).suffix
                nameContext = naming_tokens.build_movie_context(dict(movie), source_path, torrent.name)
                folder_name = naming_tokens.render(
                    folder_pattern,
                    nameContext,
                    illegal_replacement=illegal_replacement,
                    colon_replacement=colon_replacement,
                )
                filename = naming_tokens.render(
                    naming_pattern,
                    nameContext,
                    illegal_replacement=illegal_replacement,
                    colon_replacement=colon_replacement,
                    extension=source_ext,
                )
                destination_path = os.path.join(root_path, folder_name, filename)
                if keep_versions:
                    destination_path = _unique_destination(destination_path)

                try:
                    organize_file_hardlink(file_manager, source_path, destination_path)
                except Exception as e:
                    print(f"Hardlink failed: {e}. This should not happen - check folder configuration.")
                    raise
                final_path = destination_path
                file_size = os.path.getsize(final_path) if os.path.exists(final_path) else torrent.size

                movieFolder = os.path.dirname(final_path)
                try:
                    await artwork.write_video_artwork(movieFolder, movie["poster_path"], movie["backdrop_path"])
                    if profile.get("media_server") == "jellyfin":
                        nfo.write_movie_nfo(movieFolder, dict(movie))
                except Exception as e:
                    print(f"Could not write movie artwork/nfo: {e}")

                media_update = (
                    "UPDATE movies SET status = 'completed', has_file = TRUE, file_path = $1, "
                    "file_size = $2, quality_detected = $3, root_folder_id = $4, updated_at = NOW() WHERE id = $5",
                    (final_path, file_size, quality_detected, root_folder_id, media_id),
                )
                media_file_rows.append((final_path, media_files.attrs_from_metadata(final_path, file_metadata, False)))
                subtitle_dispatch.append(("movie", final_path))
                transcode_dispatch.append(("movie", final_path))
                replace_new_path = final_path

        elif media_type == "show":
            show = await conn.fetchrow(
                """
                SELECT title, tmdb_id, tvdb_id, first_air_date, poster_path, backdrop_path,
                       overview, genres
                FROM shows WHERE id = $1
                """,
                media_id,
            )
            if not show:
                print(f"Show not found: {media_id}")
                await conn.execute(_MARK_DOWNLOAD_COMPLETED, torrent.hash)
                return

            title = show["title"]
            showRow = dict(show)
            naming_pattern = profile.get("show_naming_format") or "{Show Title} - S{Season:00}E{Episode:00}"
            folder_pattern = profile.get("show_folder_format") or "{Show Title}/Season {Season:00}"

            video_files = file_manager.extract_all_videos(torrent.save_path)
            if not video_files:
                print(f"No video files found in {torrent.save_path}")
                media_update = (
                    "UPDATE shows SET status = 'completed', has_file = TRUE, file_path = $1, "
                    "file_size = $2, root_folder_id = $3, updated_at = NOW() WHERE id = $4",
                    (torrent.save_path, torrent.size, root_folder_id, media_id),
                )
            else:
                organized_paths = []
                total_size = 0
                quality_detected = None
                first_meta = None

                for source_path in video_files:
                    episode_info = parse_episode_info(Path(source_path).name)
                    if episode_info["episode_number"] is None:
                        from app.services.import_queue import queue_unmatched_file

                        await queue_unmatched_file(
                            conn, torrent.hash, torrent.name, source_path, media_type, media_id, root_folder_id
                        )
                        continue

                    if quality_detected is None:
                        first_meta = await asyncio.to_thread(metadata_extractor.extract_metadata, source_path)
                        quality_detected = first_meta.get("quality") if first_meta else None

                    source_ext = Path(source_path).suffix
                    episodeInfo = {
                        "season_number": episode_info["season_number"] or 1,
                        "episode_number": episode_info["episode_number"],
                        "episode_title": episode_info.get("episode_title") or "",
                    }
                    nameContext = naming_tokens.build_show_context(
                        showRow, episodeInfo, source_path, Path(source_path).name
                    )
                    folder_name = naming_tokens.render(
                        folder_pattern,
                        nameContext,
                        illegal_replacement=illegal_replacement,
                        colon_replacement=colon_replacement,
                    )
                    filename = naming_tokens.render(
                        naming_pattern,
                        nameContext,
                        illegal_replacement=illegal_replacement,
                        colon_replacement=colon_replacement,
                        extension=source_ext,
                    )
                    destination_path = os.path.join(root_path, folder_name, filename)
                    if keep_versions:
                        destination_path = _unique_destination(destination_path)

                    try:
                        organize_file_hardlink(file_manager, source_path, destination_path)
                        organized_paths.append(destination_path)
                        if os.path.exists(destination_path):
                            total_size += os.path.getsize(destination_path)
                    except Exception as e:
                        print(f"Hardlink failed for episode: {e}. Check folder configuration.")
                        raise

                final_path = organized_paths[0] if organized_paths else torrent.save_path

                if organized_paths:
                    rel = os.path.relpath(organized_paths[0], root_path)
                    showFolder = os.path.join(root_path, rel.split(os.sep)[0])
                    try:
                        await artwork.write_video_artwork(showFolder, show["poster_path"], show["backdrop_path"])
                        if profile.get("media_server") == "jellyfin":
                            nfo.write_tvshow_nfo(showFolder, dict(show))
                    except Exception as e:
                        print(f"Could not write show artwork/nfo: {e}")

                media_update = (
                    "UPDATE shows SET status = 'completed', has_file = TRUE, file_path = $1, "
                    "file_size = $2, quality_detected = $3, root_folder_id = $4, updated_at = NOW() WHERE id = $5",
                    (final_path, total_size or torrent.size, quality_detected, root_folder_id, media_id),
                )
                if organized_paths and first_meta is not None:
                    media_file_rows.append(
                        (final_path, media_files.attrs_from_metadata(final_path, first_meta, False))
                    )
                subtitle_dispatch = [("show", path) for path in organized_paths]
                transcode_dispatch = [("show", path) for path in organized_paths]
                if organized_paths:
                    replace_new_path = final_path

        elif media_type == "anime":
            anime = await conn.fetchrow(
                """
                SELECT title, season_year, tmdb_id, anilist_id, mal_id, poster_path,
                       backdrop_path, overview
                FROM anime WHERE id = $1
                """,
                media_id,
            )
            if not anime:
                print(f"Anime not found: {media_id}")
                await conn.execute(_MARK_DOWNLOAD_COMPLETED, torrent.hash)
                return

            title = anime["title"]
            animeRow = dict(anime)
            naming_pattern = profile.get("anime_naming_format") or "{Anime Title} - {Episode:00}"
            folder_pattern = profile.get("anime_folder_format") or "{Anime Title}"

            video_files = file_manager.extract_all_videos(torrent.save_path)
            if not video_files:
                print(f"No video files found in {torrent.save_path}")
                media_update = (
                    "UPDATE anime SET status = 'completed', has_file = TRUE, file_path = $1, "
                    "file_size = $2, root_folder_id = $3, updated_at = NOW() WHERE id = $4",
                    (torrent.save_path, torrent.size, root_folder_id, media_id),
                )
            else:
                organized_paths = []
                total_size = 0
                quality_detected = None
                first_meta = None

                for source_path in video_files:
                    episode_info = parse_episode_info(Path(source_path).name)
                    if episode_info["episode_number"] is None:
                        from app.services.import_queue import queue_unmatched_file

                        await queue_unmatched_file(
                            conn, torrent.hash, torrent.name, source_path, media_type, media_id, root_folder_id
                        )
                        continue

                    if quality_detected is None:
                        first_meta = await asyncio.to_thread(metadata_extractor.extract_metadata, source_path)
                        quality_detected = first_meta.get("quality") if first_meta else None

                    source_ext = Path(source_path).suffix
                    episodeInfo = {
                        "season_number": episode_info.get("season_number") or 1,
                        "episode_number": episode_info["episode_number"],
                        "episode_title": episode_info.get("episode_title") or "",
                        "absolute_episode": episode_info.get("absolute_episode"),
                    }
                    nameContext = naming_tokens.build_anime_context(
                        animeRow, episodeInfo, source_path, Path(source_path).name
                    )
                    folder_name = naming_tokens.render(
                        folder_pattern,
                        nameContext,
                        illegal_replacement=illegal_replacement,
                        colon_replacement=colon_replacement,
                    )
                    filename = naming_tokens.render(
                        naming_pattern,
                        nameContext,
                        illegal_replacement=illegal_replacement,
                        colon_replacement=colon_replacement,
                        extension=source_ext,
                    )
                    destination_path = os.path.join(root_path, folder_name, filename)
                    if keep_versions:
                        destination_path = _unique_destination(destination_path)

                    try:
                        organize_file_hardlink(file_manager, source_path, destination_path)
                        organized_paths.append(destination_path)
                        if os.path.exists(destination_path):
                            total_size += os.path.getsize(destination_path)
                    except Exception as e:
                        print(f"Hardlink failed for anime episode: {e}. Check folder configuration.")
                        raise

                final_path = organized_paths[0] if organized_paths else torrent.save_path

                if organized_paths:
                    rel = os.path.relpath(organized_paths[0], root_path)
                    animeFolder = os.path.join(root_path, rel.split(os.sep)[0])
                    try:
                        await artwork.write_video_artwork(animeFolder, anime["poster_path"], anime["backdrop_path"])
                        if profile.get("media_server") == "jellyfin":
                            nfo.write_tvshow_nfo(animeFolder, dict(anime))
                    except Exception as e:
                        print(f"Could not write anime artwork/nfo: {e}")

                media_update = (
                    "UPDATE anime SET status = 'completed', has_file = TRUE, file_path = $1, "
                    "file_size = $2, quality_detected = $3, root_folder_id = $4, updated_at = NOW() WHERE id = $5",
                    (final_path, total_size or torrent.size, quality_detected, root_folder_id, media_id),
                )
                if organized_paths and first_meta is not None:
                    media_file_rows.append(
                        (final_path, media_files.attrs_from_metadata(final_path, first_meta, False))
                    )
                transcode_dispatch = [("anime", path) for path in organized_paths]
                if organized_paths:
                    replace_new_path = final_path

        elif media_type == "album":
            album = await conn.fetchrow(
                """
                SELECT a.*, ar.name as artist_name, ar.picture_xl as artist_picture_xl
                FROM albums a
                LEFT JOIN artists ar ON a.artist_id = ar.id
                WHERE a.id = $1
                """,
                media_id,
            )
            if not album:
                print(f"Album not found: {media_id}")
                await conn.execute(_MARK_DOWNLOAD_COMPLETED, torrent.hash)
                return

            title = album["title"]
            artist_name = album["artist_name"] or "Unknown Artist"
            year = album["release_date"].year if album["release_date"] else None
            albumGenres = album.get("genres") or []
            album_genre = None
            if albumGenres:
                first = albumGenres[0]
                album_genre = first.get("name") if isinstance(first, dict) else first

            artist_folder_pattern = profile.get("music_artist_folder_format") or "{artist}"
            album_folder_pattern = profile.get("music_album_folder_format") or "{album} ({year})"
            track_naming_pattern = profile.get("music_track_naming_format") or "{track:00} - {title}"
            multi_disc_pattern = profile.get("music_multi_disc_format") or "{disc:00}-{track:00} - {title}"

            track_rows = await conn.fetch(
                """
                SELECT disk_number, track_position, title, duration
                FROM tracks
                WHERE album_id = $1
                ORDER BY disk_number, track_position
                """,
                media_id,
            )
            is_multi_disc = any((t["disk_number"] or 1) > 1 for t in track_rows)

            embed_artwork = bool(profile.get("music_embed_artwork"))
            embed_lyrics = bool(profile.get("music_embed_lyrics"))
            cover_bytes = None
            if embed_artwork:
                cover_bytes = await artwork.download_image(album.get("cover_xl") or album.get("cover_big"))

            audio_files = file_manager.extract_all_audio(torrent.save_path)
            if not audio_files:
                print(f"No audio files found in {torrent.save_path}")
                media_update = (
                    "UPDATE albums SET status = 'completed', has_file = TRUE, file_path = $1, "
                    "root_folder_id = $2, updated_at = NOW() WHERE id = $3",
                    (torrent.save_path, root_folder_id, media_id),
                )
            else:
                organized_paths = []
                total_size = 0
                detected_tiers = []
                use_track_meta = len(track_rows) == len(audio_files)

                for idx, source_path in enumerate(audio_files, start=1):
                    source_ext = Path(source_path).suffix
                    track_filename = Path(source_path).stem

                    src_meta = None
                    src_audio = None
                    try:
                        src_meta = await asyncio.to_thread(metadata_extractor.extract_metadata, source_path)
                        src_streams = (src_meta or {}).get("audio") or []
                        src_audio = src_streams[0] if src_streams else None
                    except Exception:
                        src_meta = None
                        src_audio = None
                    track_tier = music_quality.tier_from_audio_info(src_audio) if src_audio else None
                    if track_tier:
                        detected_tiers.append(track_tier)
                    track_format = (src_audio.get("codec") or "").upper() if src_audio else None
                    track_bitrate = None
                    if src_audio and src_audio.get("bit_rate"):
                        track_bitrate = str(int(src_audio["bit_rate"]) // 1000)
                    track_quality = music_quality.label(track_tier) if track_tier else None

                    if use_track_meta:
                        meta = track_rows[idx - 1]
                        disc_number = meta["disk_number"] or 1
                        track_number = meta["track_position"] or idx
                        track_title = meta["title"] or track_filename
                        track_duration = meta["duration"]
                    else:
                        disc_number = 1
                        track_number = idx
                        track_title = track_filename
                        track_duration = None

                    track_data = {
                        "artist": artist_name,
                        "albumartist": artist_name,
                        "album": title,
                        "year": year,
                        "track_number": track_number,
                        "disc_number": disc_number,
                        "title": track_title,
                        "genre": album_genre,
                        "format": track_format,
                        "bitrate": track_bitrate,
                        "quality": track_quality,
                        "extension": source_ext,
                    }
                    active_track_pattern = multi_disc_pattern if is_multi_disc else track_naming_pattern

                    artist_folder = file_manager.format_music_filename(
                        pattern=artist_folder_pattern,
                        track_data=track_data,
                        include_extension=False,
                        illegal_replacement=illegal_replacement,
                        colon_replacement=colon_replacement,
                    )
                    album_folder = file_manager.format_music_filename(
                        pattern=album_folder_pattern,
                        track_data=track_data,
                        include_extension=False,
                        illegal_replacement=illegal_replacement,
                        colon_replacement=colon_replacement,
                    )
                    track_name = file_manager.format_music_filename(
                        pattern=active_track_pattern,
                        track_data=track_data,
                        include_extension=True,
                        illegal_replacement=illegal_replacement,
                        colon_replacement=colon_replacement,
                    )
                    destination_path = os.path.join(root_path, artist_folder, album_folder, track_name)
                    if keep_versions:
                        destination_path = _unique_destination(destination_path)

                    try:
                        organize_file_hardlink(file_manager, source_path, destination_path)
                        organized_paths.append(destination_path)
                        if os.path.exists(destination_path):
                            total_size += os.path.getsize(destination_path)
                    except Exception as e:
                        print(f"Hardlink failed for audio file: {e}. Check folder configuration.")
                        raise

                    try:
                        music_tagging.write_tags(
                            destination_path,
                            {
                                "title": track_title,
                                "artist": artist_name,
                                "album": title,
                                "albumartist": artist_name,
                                "date": year,
                                "track": track_number,
                                "disc": disc_number,
                                "genre": album_genre,
                            },
                        )
                        if embed_artwork and cover_bytes:
                            music_tagging.embed_artwork(destination_path, cover_bytes)
                        if embed_lyrics:
                            plain, _synced = await music_tagging.fetch_lyrics(
                                artist_name, track_title, title, track_duration
                            )
                            if plain:
                                music_tagging.embed_lyrics(destination_path, plain)
                    except Exception as e:
                        print(f"Could not tag audio file {destination_path}: {e}")

                    media_file_rows.append(
                        (destination_path, media_files.attrs_from_metadata(destination_path, src_meta, True))
                    )

                # The album's stored tier is the lowest across its tracks, so it is rated
                # by its weakest file. This is the authoritative quality later upgrade
                # decisions compare against.
                detected_tier = min(detected_tiers, key=music_quality.rank) if detected_tiers else None
                album_folder_path = os.path.dirname(organized_paths[0]) if organized_paths else torrent.save_path

                if organized_paths:
                    try:
                        await artwork.write_album_cover(
                            album_folder_path, album.get("cover_xl") or album.get("cover_big")
                        )
                        artistFolder = os.path.dirname(album_folder_path)
                        if album.get("artist_picture_xl"):
                            await artwork.write_artist_image(artistFolder, album["artist_picture_xl"])
                    except Exception as e:
                        print(f"Could not write album/artist artwork: {e}")

                media_update = (
                    "UPDATE albums SET status = 'completed', has_file = TRUE, file_path = $1, "
                    "quality_detected = $2, root_folder_id = $3, updated_at = NOW() WHERE id = $4",
                    (album_folder_path, detected_tier, root_folder_id, media_id),
                )
                if organized_paths:
                    replace_new_path = album_folder_path

        else:
            title = "Media"

        # ---- Commit phase (short transaction: mark completed + update the media row) ----
        async with conn.transaction():
            await conn.execute(_MARK_DOWNLOAD_COMPLETED, torrent.hash)
            if media_update:
                await conn.execute(media_update[0], *media_update[1])

        # ---- Post-commit phase (best-effort, never blocks the completion) ----
        # Persist per-file metadata so the file panel is a plain read. The read path
        # backfills anything missing, so a failure here is not fatal.
        if media_file_rows:
            try:
                async with conn.transaction():
                    for path, attrs in media_file_rows:
                        await media_files.store(conn, media_type, media_id, path, attrs)
            except Exception as e:
                print(f"Could not persist media_files rows: {e}")

        if replace_new_path:
            apply_replace_policy(grab_mode, replace_policy, old_file_path, replace_new_path)

        if subtitle_dispatch:
            try:
                from app.tasks.subtitle_search import search_subtitles

                for sub_media_type, sub_path in subtitle_dispatch:
                    search_subtitles.delay(media_id, sub_media_type, sub_path)
            except Exception as e:
                print(f"Could not queue subtitle search: {e}")

        # Evaluate on_download transcoding rules against each video file that landed. Every
        # episode of a season pack is checked, not just the first, since a rule matching on
        # codec or resolution applies per file. Each check reads the file with ffprobe, so
        # it runs as its own task rather than holding up the rest of this import.
        if transcode_dispatch and media_id:
            try:
                from app.tasks.transcoding import check_and_apply_transcoding_rules

                for tr_media_type, tr_path in transcode_dispatch:
                    check_and_apply_transcoding_rules.delay(media_id, tr_media_type, tr_path)
            except Exception as e:
                print(f"Could not queue transcoding rule check: {e}")

        for user_id in webtransport_manager.get_active_users():
            await webtransport_manager.send_download_complete(user_id, media_id, media_type, title)

        print(f"Download completed and organized: {title}")

    except Exception as e:
        print(f"Error handling completed download: {e}")
        import traceback

        traceback.print_exc()
