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
from app.services import media_status
from app.services import torrent_contents
from app.core.cache import cacheSet
from app.services.jellyfin import queueLibraryUpdate, UPDATE_CREATED, UPDATE_DELETED

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
            mp.music_embed_artwork,
            mp.import_extra_files,
            mp.never_import_extensions
        FROM {table} m
        LEFT JOIN media_profiles mp ON m.media_profile_id = mp.id
        WHERE m.id = $1
        """,
        media_id,
    )

    if not result:
        return {}

    return dict(result)


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
        await handle_completed_download(conn, download_dict, torrent, client)
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


def _replaceTargetProblem(old_path, new_path, root_path, download_path, media_type):
    """
    Why the previous upgrade target must not be deleted, or None when it is safe. The old
    path has to sit inside the root folder and outside the download folder. Video items
    may only delete a file. Albums may delete their own album folder, which has to be at
    least artist/album deep and must not contain the new files.
    """
    if not torrent_contents.isUnderPath(old_path, root_path):
        return "outside the root folder"
    if os.path.realpath(old_path) == os.path.realpath(root_path):
        return "is the root folder itself"
    if download_path and torrent_contents.isUnderPath(old_path, download_path):
        return "inside the download folder"
    if media_type == "album":
        if not os.path.isdir(old_path):
            return "album path is not a folder"
        depth = len(os.path.relpath(os.path.realpath(old_path), os.path.realpath(root_path)).split(os.sep))
        if depth < 2:
            return "album folder is not inside an artist folder"
        if torrent_contents.isUnderPath(new_path, old_path) or torrent_contents.isUnderPath(old_path, new_path):
            return "old and new album folders overlap"
        return None
    if not os.path.isfile(old_path):
        return "not a file"
    return None


def _sidecarFiles(video_path):
    """Subtitle files beside a video that share its name, such as Movie.en.srt for Movie.mkv."""
    folder = os.path.dirname(video_path)
    stem = Path(video_path).stem
    sidecars = []
    try:
        for name in os.listdir(folder):
            candidate = os.path.join(folder, name)
            if (
                name.startswith(f"{stem}.")
                and Path(name).suffix.lower() in torrent_contents.SUBTITLE_EXTENSIONS
                and os.path.isfile(candidate)
            ):
                sidecars.append(candidate)
    except OSError:
        pass
    return sidecars


def apply_replace_policy(grab_mode, policy, old_file_path, new_file_path, root_path, download_path, media_type):
    """
    Handle the previous file when an upgrade is imported. delete_old removes it (the only
    path that deletes a file, and only because the profile opts in) after checking that
    it is the item's own library file. keep_old and keep_versions leave it in place.
    keep_versions relies on the new file being written to a distinct name (see the
    keep_versions handling in the organize phase), so both versions coexist.
    """
    if grab_mode != "upgrade" or not old_file_path:
        return
    if os.path.normpath(old_file_path) == os.path.normpath(new_file_path):
        return  # written in place, nothing to clean up
    if policy != "delete_old":
        print(f"Upgrade: kept previous file (policy={policy}): {old_file_path}")
        return

    problem = _replaceTargetProblem(old_file_path, new_file_path, root_path, download_path, media_type)
    if problem:
        print(f"Upgrade: did not remove previous path {old_file_path} because it is {problem}")
        return
    try:
        if media_type == "album":
            shutil.rmtree(old_file_path)
            print(f"Upgrade: removed replaced album folder {old_file_path}")
        else:
            for sidecar in _sidecarFiles(old_file_path):
                os.remove(sidecar)
            os.remove(old_file_path)
            print(f"Upgrade: removed replaced file {old_file_path}")
        queueLibraryUpdate([old_file_path], UPDATE_DELETED)
    except OSError as e:
        print(f"Could not remove replaced path {old_file_path}: {e}")


# Status a show or anime takes after an episode import. The finished download is already
# marked completed, so any download still active for the series keeps it downloading.
_SERIES_STATUS_AFTER_IMPORT = (
    "CASE WHEN EXISTS (SELECT 1 FROM download_history WHERE media_type = '{mediaType}' "
    "AND media_id = $2 AND status = ANY($3::text[])) THEN 'downloading' ELSE 'completed' END"
)


async def _markImportFailed(conn, torrent_hash, media_type, media_id, reason):
    """
    Record an import that brought nothing into the library. The download history row gets
    the import_failed status and reason. Once no other download of the item is active, the
    item leaves downloading, back to completed when it already has a file (a failed
    upgrade, or other episodes of a show) and to wanted otherwise.
    """
    async with conn.transaction():
        await conn.execute(
            "UPDATE download_history SET status = 'import_failed', error_message = $2, "
            "updated_at = NOW() WHERE torrent_hash = $1",
            torrent_hash,
            f"Import failed: {reason}",
        )
        await media_status.releaseDownloadingStatus(conn, media_type, media_id)
    print(f"Import failed for {torrent_hash}: {reason}")


async def _recordEpisodeFiles(conn, episodeTable, media_id, episode_imports):
    """
    Mark each imported episode as having its file. Episodes are matched by season and
    episode number. An anime file numbered only by episode, with season assumed to be 1,
    falls back to the single episode row with that number when no row matches exactly.
    """
    table, parentColumn = episodeTable
    for season, episode, path, size, quality in episode_imports:
        updated = await conn.fetchval(
            f"UPDATE {table} SET has_file = TRUE, file_path = $4, file_size = $5, quality_detected = $6, "
            f"updated_at = NOW() WHERE {parentColumn} = $1 AND season_number = $2 AND episode_number = $3 "
            f"RETURNING id",
            media_id,
            season,
            episode,
            path,
            size,
            quality,
        )
        if updated is None and table == "anime_episodes":
            matches = await conn.fetch(
                f"SELECT id FROM {table} WHERE {parentColumn} = $1 AND episode_number = $2", media_id, episode
            )
            if len(matches) == 1:
                updated = await conn.fetchval(
                    f"UPDATE {table} SET has_file = TRUE, file_path = $2, file_size = $3, quality_detected = $4, "
                    f"updated_at = NOW() WHERE id = $1 RETURNING id",
                    matches[0]["id"],
                    path,
                    size,
                    quality,
                )
        if updated is None:
            print(f"No {table} row for season {season} episode {episode}, file imported at {path}")


def _videoProbeProblem(metadata):
    """Why ffprobe's result rules a file out as video, or None when it has a video stream."""
    if not metadata:
        return "ffprobe could not read it"
    if not metadata.get("video"):
        return "it has no video stream"
    return None


def _splitEpisodeVideos(contents):
    """Episode videos in torrent order, and videos inside extras folders."""
    episodes = []
    extras = []
    for video in sorted(contents.videos, key=lambda f: f.relativePath.lower()):
        (extras if torrent_contents.extrasFolderFor(video) else episodes).append(video)
    return episodes, extras


def _noEpisodesReason(queued_count):
    """Failure reason when a show or anime torrent brought no episode into the library."""
    if queued_count:
        return (
            f"no episode could be matched automatically, {queued_count} file(s) are waiting in the manual import queue"
        )
    return "no episode video in the torrent"


def _skippedSummary(contents):
    """A short list of skipped file names for logs and failure reasons."""
    names = [Path(f.relativePath).name for f in contents.skipped[:3]]
    more = len(contents.skipped) - len(names)
    return ", ".join(names) + (f" and {more} more" if more > 0 else "")


def _linkMedia(file_manager, source_path, destination_path, replace_existing, keep_versions):
    """Link a video or track into the library. A different file already at the destination is kept and the new one gets a version suffix."""
    if keep_versions or (
        os.path.exists(destination_path)
        and not replace_existing
        and not os.path.samefile(source_path, destination_path)
    ):
        destination_path = _unique_destination(destination_path)
    return file_manager.link_into_library(source_path, destination_path, replace_existing)


def _linkSubtitles(file_manager, video, destination_video_path, subtitles):
    """Link subtitles beside a renamed video as name.tag.ext. Returns the linked paths."""
    linked = []
    destinationBase = os.path.splitext(destination_video_path)[0]
    for subtitle in subtitles:
        tag = torrent_contents.subtitleTag(subtitle, video.stem)
        name = f"{destinationBase}.{tag}{subtitle.extension}" if tag else f"{destinationBase}{subtitle.extension}"
        try:
            linked.append(file_manager.link_into_library(subtitle.absolutePath, torrent_contents.uniquePath(name)))
        except OSError as e:
            print(f"Could not link subtitle {subtitle.relativePath}: {e}")
    return linked


def _linkExtras(file_manager, videos, item_folder, default_folder="Extras"):
    """Link extra videos into the item folder under their extras folder name."""
    for video in videos:
        folder = torrent_contents.extrasFolderFor(video) or default_folder
        destination = os.path.join(item_folder, folder, Path(video.relativePath).name)
        try:
            file_manager.link_into_library(video.absolutePath, torrent_contents.uniquePath(destination))
        except OSError as e:
            print(f"Could not link extra {video.relativePath}: {e}")


def _linkImages(file_manager, images, folder):
    """Link torrent images into a folder, renaming any that collide with Kinora's own artwork names."""
    for image in images:
        destination = os.path.join(folder, torrent_contents.safeImageName(image))
        try:
            file_manager.link_into_library(image.absolutePath, torrent_contents.uniquePath(destination))
        except OSError as e:
            print(f"Could not link image {image.relativePath}: {e}")


def _linkMusicCompanions(file_manager, companions, images, album_folder, audio_root, track_names):
    """
    Link music companion files (lyrics, cue sheets, rip logs, booklets, scans) into the
    album folder, keeping their folder structure relative to the audio. A .lrc file that
    matches a source track is renamed to match the renamed track.
    """
    for companion in companions + images:
        relative = (
            os.path.relpath(companion.absolutePath, audio_root) if audio_root else Path(companion.relativePath).name
        )
        if relative.startswith(".."):
            relative = Path(companion.relativePath).name
        if companion.extension == ".lrc" and companion.stem.lower() in track_names:
            relative = os.path.join(os.path.dirname(relative), track_names[companion.stem.lower()] + ".lrc")
        elif companion.extension in torrent_contents.IMAGE_EXTENSIONS:
            relative = os.path.join(os.path.dirname(relative), torrent_contents.safeImageName(companion))
        destination = os.path.join(album_folder, relative)
        try:
            file_manager.link_into_library(companion.absolutePath, torrent_contents.uniquePath(destination))
        except OSError as e:
            print(f"Could not link music file {companion.relativePath}: {e}")


async def handle_completed_download(conn, download_record, torrent, client=None):
    """
    Handle post-processing for a completed download.

    Only the torrent's own files, taken from the download client's file list, are
    imported. All slow work (organizing with hardlinks, ffprobe, tagging, artwork) runs
    with no transaction held. Only the final download-history and media-row writes are
    wrapped in a short transaction, so a connection is never held open across file I/O.
    If organizing raises, the download is never marked completed and is retried next
    cycle. When nothing can be imported, the download is marked import_failed.
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
        download_path = root_folder.get("download_path")

        file_manager = FileManager()
        metadata_extractor = MetadataExtractor()

        profile = await get_profile_settings(conn, media_id, media_type)
        illegal_replacement = profile.get("illegal_char_replacement") or ""
        colon_replacement = profile.get("colon_replacement") or " -"

        if client is None:
            client = await get_qbittorrent_client()
        torrentFiles = await torrent_contents.getTorrentFiles(client, torrent) if client else []
        if not torrentFiles:
            await _markImportFailed(
                conn, torrent.hash, media_type, media_id, "the download client returned no files for this torrent"
            )
            return
        import_extras = profile.get("import_extra_files")
        import_extras = True if import_extras is None else bool(import_extras)
        contents = torrent_contents.sortContents(
            torrentFiles, torrent_contents.neverImportList(profile.get("never_import_extensions"))
        )
        if contents.skipped:
            print(f"Not importing {len(contents.skipped)} file(s) from {torrent.name}: {_skippedSummary(contents)}")

        grab_mode = download_record.get("grab_mode") or "auto"
        replace_policy = profile.get("upgrade_replace_policy") or "keep_old"
        old_file_path = None
        if grab_mode == "upgrade" and media_type in ("movie", "album"):
            _table = {"movie": "movies", "album": "albums"}[media_type]
            old_file_path = await conn.fetchval(f"SELECT file_path FROM {_table} WHERE id = $1", media_id)
        # Shows and anime track files per episode, so the previous file of each upgraded
        # episode is looked up by season and episode number.
        oldEpisodePaths = {}
        episodeTable = {"show": ("episodes", "show_id"), "anime": ("anime_episodes", "anime_id")}.get(media_type)
        if grab_mode == "upgrade" and episodeTable:
            rows = await conn.fetch(
                f"SELECT season_number, episode_number, file_path FROM {episodeTable[0]} "
                f"WHERE {episodeTable[1]} = $1 AND file_path IS NOT NULL",
                media_id,
            )
            oldEpisodePaths = {(r["season_number"], r["episode_number"]): r["file_path"] for r in rows}
            # Anime rows can lack a season number while imported files assume season 1, so
            # an episode number held by a single row also finds that row's file.
            if media_type == "anime":
                byEpisode = {}
                for r in rows:
                    byEpisode.setdefault(r["episode_number"], []).append(r["file_path"])
                for episodeNumber, paths in byEpisode.items():
                    if len(paths) == 1:
                        oldEpisodePaths.setdefault((None, episodeNumber), paths[0])
        # When keeping versions, an upgrade must not overwrite the existing file, so each
        # organized path is made unique before linking. Off for other policies so normal
        # names are untouched.
        keep_versions = grab_mode == "upgrade" and replace_policy == "keep_versions"
        # Only an upgrade under delete_old may replace a file already at the destination.
        replace_existing = grab_mode == "upgrade" and replace_policy == "delete_old"

        # Outputs collected by the organize phase, applied afterward. No transaction is
        # held while these are produced.
        title = "Media"
        media_update = None  # (sql, params) for the media-row update, or None
        media_file_rows = []  # list of (file_path, attrs) to persist into media_files
        subtitle_dispatch = []  # list of (media_type, path) to queue subtitle searches for
        transcode_dispatch = []  # list of (media_type, path) to evaluate transcoding rules against
        replace_new_path = None  # organized path for the upgrade replace policy
        episode_imports = []  # (season, episode, path, size, quality) per imported episode

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
            mainVideo = max(contents.videos, key=lambda f: f.size) if contents.videos else None

            if not mainVideo:
                await _markImportFailed(conn, torrent.hash, media_type, media_id, "no video file in the torrent")
                return
            else:
                source_path = mainVideo.absolutePath
                file_metadata = await asyncio.to_thread(metadata_extractor.extract_metadata, source_path)
                probeProblem = _videoProbeProblem(file_metadata)
                if probeProblem:
                    await _markImportFailed(
                        conn,
                        torrent.hash,
                        media_type,
                        media_id,
                        f"{Path(source_path).name} is not a playable video because {probeProblem}",
                    )
                    return
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

                try:
                    final_path = _linkMedia(
                        file_manager, source_path, destination_path, replace_existing, keep_versions
                    )
                except Exception as e:
                    print(f"Hardlink failed: {e}. This should not happen - check folder configuration.")
                    raise
                file_size = os.path.getsize(final_path) if os.path.exists(final_path) else torrent.size

                movieFolder = os.path.dirname(final_path)
                if import_extras:
                    _linkSubtitles(
                        file_manager,
                        mainVideo,
                        final_path,
                        torrent_contents.subtitlesForVideo(
                            mainVideo,
                            contents.subtitles,
                            sum(1 for v in contents.videos if not torrent_contents.extrasFolderFor(v)) == 1,
                        ),
                    )
                    _linkExtras(file_manager, [v for v in contents.videos if v is not mainVideo], movieFolder)
                    _linkImages(file_manager, contents.images, movieFolder)
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

            episodeVideos, extraVideos = _splitEpisodeVideos(contents)
            if not episodeVideos and not extraVideos:
                await _markImportFailed(conn, torrent.hash, media_type, media_id, "no video file in the torrent")
                return
            else:
                organized_paths = []
                total_size = 0
                quality_detected = None
                first_meta = None
                queued_count = 0

                for episodeVideo in episodeVideos:
                    source_path = episodeVideo.absolutePath
                    episode_info = parse_episode_info(Path(source_path).name)
                    if episode_info["episode_number"] is None:
                        from app.services.import_queue import queue_unmatched_file

                        await queue_unmatched_file(
                            conn, torrent.hash, torrent.name, source_path, media_type, media_id, root_folder_id
                        )
                        queued_count += 1
                        continue

                    episodeMeta = await asyncio.to_thread(metadata_extractor.extract_metadata, source_path)
                    probeProblem = _videoProbeProblem(episodeMeta)
                    if probeProblem:
                        print(f"Skipping {Path(source_path).name}, not a playable video because {probeProblem}")
                        continue
                    if quality_detected is None:
                        first_meta = episodeMeta
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

                    try:
                        destination_path = _linkMedia(
                            file_manager, source_path, destination_path, replace_existing, keep_versions
                        )
                        organized_paths.append(destination_path)
                        episodeSize = os.path.getsize(destination_path) if os.path.exists(destination_path) else 0
                        total_size += episodeSize
                        episode_imports.append(
                            (
                                episodeInfo["season_number"],
                                episodeInfo["episode_number"],
                                destination_path,
                                episodeSize,
                                quality_detected,
                            )
                        )
                    except Exception as e:
                        print(f"Hardlink failed for episode: {e}. Check folder configuration.")
                        raise
                    if import_extras:
                        _linkSubtitles(
                            file_manager,
                            episodeVideo,
                            destination_path,
                            torrent_contents.subtitlesForVideo(
                                episodeVideo, contents.subtitles, len(episodeVideos) == 1
                            ),
                        )

                if not organized_paths:
                    await _markImportFailed(conn, torrent.hash, media_type, media_id, _noEpisodesReason(queued_count))
                    return

                final_path = organized_paths[0]

                if organized_paths:
                    rel = os.path.relpath(organized_paths[0], root_path)
                    showFolder = os.path.join(root_path, rel.split(os.sep)[0])
                    if import_extras:
                        _linkExtras(file_manager, extraVideos, showFolder)
                        _linkImages(file_manager, contents.images, showFolder)
                    try:
                        await artwork.write_video_artwork(showFolder, show["poster_path"], show["backdrop_path"])
                        if profile.get("media_server") == "jellyfin":
                            nfo.write_tvshow_nfo(showFolder, dict(show))
                    except Exception as e:
                        print(f"Could not write show artwork/nfo: {e}")

                media_update = (
                    # Another download of this show still running keeps it downloading.
                    f"UPDATE shows SET status = {_SERIES_STATUS_AFTER_IMPORT.format(mediaType='show')}, "
                    "root_folder_id = $1, updated_at = NOW() WHERE id = $2",
                    (root_folder_id, media_id, list(media_status.ACTIVE_DOWNLOAD_STATUSES)),
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

            episodeVideos, extraVideos = _splitEpisodeVideos(contents)
            if not episodeVideos and not extraVideos:
                await _markImportFailed(conn, torrent.hash, media_type, media_id, "no video file in the torrent")
                return
            else:
                organized_paths = []
                total_size = 0
                quality_detected = None
                first_meta = None
                queued_count = 0

                for episodeVideo in episodeVideos:
                    source_path = episodeVideo.absolutePath
                    episode_info = parse_episode_info(Path(source_path).name)
                    if episode_info["episode_number"] is None:
                        from app.services.import_queue import queue_unmatched_file

                        await queue_unmatched_file(
                            conn, torrent.hash, torrent.name, source_path, media_type, media_id, root_folder_id
                        )
                        queued_count += 1
                        continue

                    episodeMeta = await asyncio.to_thread(metadata_extractor.extract_metadata, source_path)
                    probeProblem = _videoProbeProblem(episodeMeta)
                    if probeProblem:
                        print(f"Skipping {Path(source_path).name}, not a playable video because {probeProblem}")
                        continue
                    if quality_detected is None:
                        first_meta = episodeMeta
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

                    try:
                        destination_path = _linkMedia(
                            file_manager, source_path, destination_path, replace_existing, keep_versions
                        )
                        organized_paths.append(destination_path)
                        episodeSize = os.path.getsize(destination_path) if os.path.exists(destination_path) else 0
                        total_size += episodeSize
                        episode_imports.append(
                            (
                                episodeInfo["season_number"],
                                episodeInfo["episode_number"],
                                destination_path,
                                episodeSize,
                                quality_detected,
                            )
                        )
                    except Exception as e:
                        print(f"Hardlink failed for anime episode: {e}. Check folder configuration.")
                        raise
                    if import_extras:
                        _linkSubtitles(
                            file_manager,
                            episodeVideo,
                            destination_path,
                            torrent_contents.subtitlesForVideo(
                                episodeVideo, contents.subtitles, len(episodeVideos) == 1
                            ),
                        )

                if not organized_paths:
                    await _markImportFailed(conn, torrent.hash, media_type, media_id, _noEpisodesReason(queued_count))
                    return

                final_path = organized_paths[0]

                if organized_paths:
                    rel = os.path.relpath(organized_paths[0], root_path)
                    animeFolder = os.path.join(root_path, rel.split(os.sep)[0])
                    if import_extras:
                        _linkExtras(file_manager, extraVideos, animeFolder)
                        _linkImages(file_manager, contents.images, animeFolder)
                    try:
                        await artwork.write_video_artwork(animeFolder, anime["poster_path"], anime["backdrop_path"])
                        if profile.get("media_server") == "jellyfin":
                            nfo.write_tvshow_nfo(animeFolder, dict(anime))
                    except Exception as e:
                        print(f"Could not write anime artwork/nfo: {e}")

                media_update = (
                    # Another download of this anime still running keeps it downloading.
                    f"UPDATE anime SET status = {_SERIES_STATUS_AFTER_IMPORT.format(mediaType='anime')}, "
                    "has_file = TRUE, root_folder_id = $1, updated_at = NOW() WHERE id = $2",
                    (root_folder_id, media_id, list(media_status.ACTIVE_DOWNLOAD_STATUSES)),
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

            # Sorted by path inside the torrent so CD1 tracks come before CD2 tracks.
            audioEntries = sorted(contents.audio, key=lambda f: f.relativePath.lower())
            audio_files = [entry.absolutePath for entry in audioEntries]
            if not audio_files:
                await _markImportFailed(conn, torrent.hash, media_type, media_id, "no audio file in the torrent")
                return
            else:
                organized_paths = []
                total_size = 0
                detected_tiers = []
                use_track_meta = len(track_rows) == len(audio_files)
                # Source track stem to renamed track stem, used to rename matching .lrc files.
                renamedTracks = {}

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

                    try:
                        destination_path = _linkMedia(
                            file_manager, source_path, destination_path, replace_existing, keep_versions
                        )
                        organized_paths.append(destination_path)
                        renamedTracks[Path(source_path).stem.lower()] = Path(destination_path).stem
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
                if not organized_paths:
                    await _markImportFailed(conn, torrent.hash, media_type, media_id, "no audio file could be linked")
                    return
                album_folder_path = os.path.dirname(organized_paths[0])

                if import_extras:
                    # Companion files keep their layout relative to the folder that holds the audio.
                    audioRoot = os.path.commonpath([os.path.dirname(p) for p in audio_files])
                    _linkMusicCompanions(
                        file_manager, contents.companions, contents.images, album_folder_path, audioRoot, renamedTracks
                    )

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
            if episode_imports and episodeTable:
                await _recordEpisodeFiles(conn, episodeTable, media_id, episode_imports)

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

        if replace_new_path and not episode_imports:
            apply_replace_policy(
                grab_mode, replace_policy, old_file_path, replace_new_path, root_path, download_path, media_type
            )
        for season, episode, newPath, _size, _quality in episode_imports:
            apply_replace_policy(
                grab_mode,
                replace_policy,
                oldEpisodePaths.get((season, episode)) or oldEpisodePaths.get((None, episode)),
                newPath,
                root_path,
                download_path,
                media_type,
            )

        # Tell Jellyfin which library folders changed. This only queues the paths, the
        # request goes out from its own task.
        jellyfinPaths = [path for path, _attrs in media_file_rows]
        jellyfinPaths.extend(newPath for _season, _episode, newPath, _size, _quality in episode_imports)
        if replace_new_path:
            jellyfinPaths.append(replace_new_path)
        queueLibraryUpdate(jellyfinPaths, UPDATE_CREATED)

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
