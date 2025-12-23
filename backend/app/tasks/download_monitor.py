import os
from datetime import datetime
from app.tasks.celery_app import celery_app, runAsync
from app.db import get_pool
from app.services.download_clients.qbittorrent import get_qbittorrent_client
from app.services.download_clients.base import TorrentState
from app.core.webtransport import webtransport_manager
from app.services.file_manager import FileManager
from app.services.metadata_extractor import MetadataExtractor


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
    try:
        # Get qBittorrent client instance
        client = await get_qbittorrent_client()
        if not client:
            return {"status": "skipped", "reason": "qBittorrent not configured"}

        # Get all active torrents from download client
        torrents = await client.get_torrents()

        if not torrents:
            return {"status": "success", "active_downloads": 0, "completed": 0}

        completed_count = 0
        pool = await get_pool()

        async with pool.acquire() as conn:
            for torrent in torrents:
                # Update progress in database
                await conn.execute(
                    """
                    UPDATE download_history
                    SET progress = $1, updated_at = NOW()
                    WHERE torrent_hash = $2 AND status IN ('downloading', 'pending')
                    """,
                    torrent.progress,
                    torrent.hash,
                )

                # Get download record
                download_record = await conn.fetchrow(
                    "SELECT * FROM download_history WHERE torrent_hash = $1",
                    torrent.hash
                )

                if not download_record:
                    continue

                # Send real-time progress update
                download_dict = dict(download_record)
                user_ids = webtransport_manager.get_active_users()
                for user_id in user_ids:
                    await webtransport_manager.send_download_update(
                        user_id,
                        torrent.hash,
                        torrent.progress,
                        torrent.download_speed
                    )

                # Handle completed downloads
                if torrent.state == TorrentState.SEEDING or torrent.progress >= 1.0:
                    if download_dict["status"] != "completed":
                        await handle_completed_download(conn, download_dict, torrent)
                        completed_count += 1

                # Handle failed downloads
                elif torrent.state == TorrentState.ERROR:
                    await conn.execute(
                        """
                        UPDATE download_history
                        SET status = 'failed', error_message = $1, updated_at = NOW()
                        WHERE torrent_hash = $2
                        """,
                        "Torrent error in download client",
                        torrent.hash
                    )

        return {
            "status": "success",
            "active_downloads": len(torrents),
            "completed": completed_count,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        print(f"Download monitoring error: {e}")
        return {"status": "error", "message": str(e)}


async def handle_completed_download(conn, download_record, torrent):
    """
    Handle post-processing for completed download.
    Organizes files using FileManager and updates database.
    """
    try:
        # Mark as completed
        await conn.execute(
            """
            UPDATE download_history
            SET status = 'completed', completed_at = NOW(), progress = 1.0, updated_at = NOW()
            WHERE torrent_hash = $1
            """,
            torrent.hash
        )

        media_id = download_record["media_id"]
        media_type = download_record["media_type"]

        # Initialize services
        file_manager = FileManager()
        metadata_extractor = MetadataExtractor()

        # Update media record based on type
        if media_type == "movie":
            # Get movie details
            movie = await conn.fetchrow(
                """
                SELECT title, release_date, tmdb_id, root_folder_path
                FROM movies WHERE id = $1
                """,
                media_id
            )

            if not movie:
                print(f"Movie not found: {media_id}")
                return

            title = movie["title"]
            year = movie["release_date"][:4] if movie["release_date"] else None

            # Find the largest video file in torrent directory
            source_path = file_manager.extract_largest_video(torrent.save_path)

            if not source_path:
                print(f"No video file found in {torrent.save_path}")
                # Update with just the torrent path
                await conn.execute(
                    """
                    UPDATE movies
                    SET status = 'completed', has_file = TRUE,
                        file_path = $1, file_size = $2, updated_at = NOW()
                    WHERE id = $3
                    """,
                    torrent.save_path,
                    torrent.size,
                    media_id
                )
                return

            # Extract metadata from file
            file_metadata = metadata_extractor.extract_metadata(source_path)
            quality_detected = file_metadata.get('quality') if file_metadata else None

            # Determine destination path
            root_folder = movie["root_folder_path"] or "/media/movies"

            # Format filename using FileManager
            formatted_filename = file_manager.format_movie_filename(
                title=title,
                year=year,
                quality=quality_detected,
                tmdb_id=movie["tmdb_id"],
                pattern="{title} ({year})"
            )

            # Construct full destination path
            destination_path = os.path.join(root_folder, formatted_filename)

            # Organize file (move to destination with proper naming)
            try:
                file_manager.organize_file(
                    source_path=source_path,
                    destination_path=destination_path,
                    operation='move'
                )

                final_path = destination_path
                file_size = os.path.getsize(final_path) if os.path.exists(final_path) else torrent.size

            except Exception as e:
                print(f"Error organizing file: {e}. Keeping original path.")
                final_path = source_path
                file_size = torrent.size

            # Update database with organized file info
            await conn.execute(
                """
                UPDATE movies
                SET status = 'completed', has_file = TRUE,
                    file_path = $1, file_size = $2, quality_detected = $3, updated_at = NOW()
                WHERE id = $4
                """,
                final_path,
                file_size,
                quality_detected,
                media_id
            )

        elif media_type == "show":
            # Get show details
            show = await conn.fetchrow(
                """
                SELECT title, root_folder_path
                FROM shows WHERE id = $1
                """,
                media_id
            )

            if not show:
                print(f"Show not found: {media_id}")
                return

            title = show["title"]

            # For shows, we need to handle individual episode files
            # This is more complex and requires season/episode detection
            # For now, just update with basic info
            source_path = file_manager.extract_largest_video(torrent.save_path)

            if source_path:
                file_metadata = metadata_extractor.extract_metadata(source_path)
                quality_detected = file_metadata.get('quality') if file_metadata else None

                await conn.execute(
                    """
                    UPDATE shows
                    SET status = 'completed', has_file = TRUE,
                        file_path = $1, file_size = $2, quality_detected = $3, updated_at = NOW()
                    WHERE id = $4
                    """,
                    source_path,
                    os.path.getsize(source_path) if os.path.exists(source_path) else torrent.size,
                    quality_detected,
                    media_id
                )
            else:
                # No video file found
                await conn.execute(
                    """
                    UPDATE shows
                    SET status = 'completed', has_file = TRUE,
                        file_path = $1, file_size = $2, updated_at = NOW()
                    WHERE id = $3
                    """,
                    torrent.save_path,
                    torrent.size,
                    media_id
                )

        elif media_type == "anime":
            # Get anime details
            anime = await conn.fetchrow(
                """
                SELECT title, season_year, anilist_id, root_folder_path
                FROM anime WHERE id = $1
                """,
                media_id
            )

            if not anime:
                print(f"Anime not found: {media_id}")
                return

            title = anime["title"]

            # Similar to shows, anime may need episode-specific handling
            source_path = file_manager.extract_largest_video(torrent.save_path)

            if source_path:
                file_metadata = metadata_extractor.extract_metadata(source_path)
                quality_detected = file_metadata.get('quality') if file_metadata else None

                await conn.execute(
                    """
                    UPDATE anime
                    SET status = 'completed', has_file = TRUE,
                        file_path = $1, file_size = $2, quality_detected = $3, updated_at = NOW()
                    WHERE id = $4
                    """,
                    source_path,
                    os.path.getsize(source_path) if os.path.exists(source_path) else torrent.size,
                    quality_detected,
                    media_id
                )
            else:
                await conn.execute(
                    """
                    UPDATE anime
                    SET status = 'completed', has_file = TRUE,
                        file_path = $1, file_size = $2, updated_at = NOW()
                    WHERE id = $3
                    """,
                    torrent.save_path,
                    torrent.size,
                    media_id
                )

        else:
            title = "Media"

        # Notify user of completion
        user_ids = webtransport_manager.get_active_users()
        for user_id in user_ids:
            await webtransport_manager.send_download_complete(
                user_id, media_id, media_type, title
            )

        print(f"Download completed and organized: {title}")

    except Exception as e:
        print(f"Error handling completed download: {e}")
        import traceback
        traceback.print_exc()
