"""
Validation Monitor (Fallback)

Celery task that monitors torrents with "validating" tag as a fallback mechanism.
Primary validation is now event-driven (triggered immediately after adding a torrent).

This task runs every 5 minutes to catch edge cases:
- Server restart while a torrent was being validated
- Network issues during the immediate validation
- Any other scenario where immediate validation didn't complete

It uses the same validation, file skipping and failure handling as the immediate path,
so a failure here is also blocklisted by hash and recorded in download history.
"""

import time
from datetime import datetime

from app.tasks.celery_app import celery_app, runAsync
from app.db import get_pool
from app.services.download_clients.qbittorrent import get_qbittorrent_client
from app.services.media_profile import MediaProfile
from app.services.torrent_validator import (
    torrent_validator,
    ValidationResult,
    write_validation_state,
    default_validation_profile,
    run_profile_validation,
    skip_never_import_files,
    handle_validation_failure,
    STEP_PASSED,
    STEP_FAILED,
    STEP_PENDING,
)
from app.core.cache import cacheSet


@celery_app.task(name="app.tasks.validation_monitor.check_validating_torrents")
def check_validating_torrents():
    """
    Monitor torrents with "validating" tag.
    Runs validation when metadata is available.
    """
    return runAsync(async_check_validating_torrents())


async def async_check_validating_torrents():
    """
    Async implementation of validation monitoring.
    """
    taskName = "validation_monitor"
    startTime = time.time()
    status = "success"

    try:
        client = await get_qbittorrent_client()
        if not client:
            return {"status": "skipped", "reason": "qBittorrent not configured"}

        # Get torrents with "validating" tag
        validating_torrents = await client.get_torrents(tag="validating")

        if not validating_torrents:
            return {"status": "success", "validating": 0, "validated": 0, "failed": 0}

        validated_count = 0
        failed_count = 0
        pending_count = 0
        pool = await get_pool()

        for torrent in validating_torrents:
            # Check if metadata is ready
            if not torrent_validator.is_metadata_ready(torrent):
                pending_count += 1
                await write_validation_state(torrent.hash, STEP_PENDING)
                continue

            # Get file list from torrent
            files = await client.get_torrent_files(torrent.hash)

            if not files:
                pending_count += 1
                await write_validation_state(torrent.hash, STEP_PENDING)
                continue

            async with pool.acquire() as conn:
                media_type, profileRow = await _get_profile_for_torrent(conn, torrent)
            profile = MediaProfile.from_row(profileRow) if profileRow else default_validation_profile()

            report = run_profile_validation(torrent_validator, files, media_type, profile)

            if report.result == ValidationResult.PASSED:
                await skip_never_import_files(client, torrent.hash, files, profile)
                await _mark_validated(client, torrent)
                validated_count += 1
                print(f"Validation passed: {torrent.name} - {report.message}")
                await write_validation_state(torrent.hash, STEP_PASSED, report)
                try:
                    from app.services.seeding import apply_seeding_limits

                    await apply_seeding_limits(client, torrent.hash, profile if profileRow else None)
                except Exception as e:
                    print(f"Could not apply seeding limits: {e}")
            else:
                await handle_validation_failure(
                    client, torrent.hash, profile.validation_failure_action, report, media_type
                )
                failed_count += 1
                print(f"Validation failed: {torrent.name} - {report.message}")
                await write_validation_state(torrent.hash, STEP_FAILED, report)

        return {
            "status": "success",
            "validating": len(validating_torrents),
            "pending": pending_count,
            "validated": validated_count,
            "failed": failed_count,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    except Exception as e:
        status = "failed"
        print(f"Validation monitoring error: {e}")
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


async def _mark_validated(client, torrent):
    """Mark torrent as validated and resume download."""
    # Remove "validating" tag and add "validated"
    await client.remove_tags(torrent.hash, ["validating"])
    await client.set_tags(torrent.hash, ["validated"])

    # Resume the torrent
    await client.resume_torrent(torrent.hash)


def _extract_media_type_from_tags(tags: list) -> str:
    """Extract media type from torrent tags."""
    if not tags:
        return "movie"

    for tag in tags:
        if tag.startswith("movie-"):
            return "movie"
        elif tag.startswith("show-"):
            return "show"
        elif tag.startswith("anime-"):
            return "anime"
        elif tag.startswith("album-"):
            return "album"

    return "movie"


async def _get_profile_for_torrent(conn, torrent):
    """
    The media type and profile row for a torrent. The download history row is checked
    first, since every tracked add records its media item there. Tags such as movie-12
    are the fallback for older adds.
    """
    history = await conn.fetchrow(
        "SELECT media_type, media_id FROM download_history WHERE torrent_hash = $1",
        torrent.hash,
    )
    if history:
        media_type, media_id = history["media_type"], history["media_id"]
    else:
        media_type = _extract_media_type_from_tags(torrent.tags)
        media_id = None
        for tag in torrent.tags or []:
            if tag.startswith(f"{media_type}-"):
                try:
                    media_id = int(tag.split("-")[1])
                    break
                except ValueError, IndexError:
                    continue

    table_name = {"movie": "movies", "show": "shows", "anime": "anime", "album": "albums"}.get(media_type)
    if not media_id or not table_name:
        return media_type, None

    media = await conn.fetchrow(f"SELECT media_profile_id FROM {table_name} WHERE id = $1", media_id)
    if not media or not media.get("media_profile_id"):
        return media_type, None

    profile = await conn.fetchrow("SELECT * FROM media_profiles WHERE id = $1", media["media_profile_id"])
    return media_type, dict(profile) if profile else None
