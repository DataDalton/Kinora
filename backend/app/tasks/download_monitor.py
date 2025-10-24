import asyncio
from datetime import datetime
from app.tasks.celery_app import celery_app
from app.core.database import get_pool
from app.services.download_clients.qbittorrent import qbittorrent_client
from app.services.download_clients.base import TorrentState
from app.core.webtransport import webtransport_manager


@celery_app.task(name="app.tasks.download_monitor.check_downloads")
def check_downloads():
    """
    Monitor download client for active downloads
    Updates progress and triggers post-processing when complete
    """
    return asyncio.run(async_check_downloads())


async def async_check_downloads():
    """
    Async implementation of download monitoring
    """
    try:
        # Get all active torrents from download client
        torrents = await qbittorrent_client.get_torrents()

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
    Handle post-processing for completed download
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

        # Update media record
        if media_type == "movie":
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

            # Get movie title for notification
            movie = await conn.fetchrow("SELECT title FROM movies WHERE id = $1", media_id)
            title = movie["title"] if movie else "Unknown"

        elif media_type == "show":
            # TODO: Handle show episode completion
            title = "Show Episode"

        else:
            title = "Media"

        # Notify user of completion
        user_ids = webtransport_manager.get_active_users()
        for user_id in user_ids:
            await webtransport_manager.send_download_complete(
                user_id, media_id, media_type, title
            )

        print(f"Download completed: {title}")

    except Exception as e:
        print(f"Error handling completed download: {e}")
