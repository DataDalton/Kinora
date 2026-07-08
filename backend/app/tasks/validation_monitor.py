"""
Validation Monitor (Fallback)

Celery task that monitors torrents with "validating" tag as a fallback mechanism.
Primary validation is now event-driven (triggered immediately after adding a torrent).

This task runs every 5 minutes to catch edge cases:
- Server restart while a torrent was being validated
- Network issues during the immediate validation
- Any other scenario where immediate validation didn't complete
"""

import time
from datetime import datetime

from app.tasks.celery_app import celery_app, runAsync
from app.db import get_pool
from app.services.download_clients.qbittorrent import get_qbittorrent_client
from app.services.torrent_validator import (
    torrent_validator,
    ValidationResult,
    write_validation_state,
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

        async with pool.acquire() as conn:
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

                # Determine media type from tags
                media_type = _extract_media_type_from_tags(torrent.tags)

                # Get media profile for validation settings
                profile = await _get_profile_for_torrent(conn, torrent, media_type)

                # Check if validation is enabled
                if profile and not profile.get("validation_enabled", True):
                    # Skip validation, just mark as validated and resume
                    await _mark_validated(client, torrent)
                    validated_count += 1
                    print(f"Validation skipped (disabled in profile): {torrent.name}")
                    await write_validation_state(torrent.hash, STEP_PASSED)
                    continue

                # Get extension settings from profile
                allowed = None
                forbidden = None
                failure_action = "pause_notify"
                validation_mode = "allowlist"

                if profile:
                    # Get media-type specific allowed extensions
                    allowed = profile.get(f"{media_type}_allowed_extensions")
                    forbidden = profile.get("forbidden_extensions")
                    failure_action = profile.get("validation_failure_action", "pause_notify")
                    validation_mode = profile.get("validation_mode", "allowlist")

                # Run validation
                report = torrent_validator.validate_files(
                    files=files,
                    media_type=media_type,
                    allowed_extensions=allowed,
                    forbidden_extensions=forbidden,
                    mode=validation_mode,
                )

                if report.result == ValidationResult.PASSED:
                    # Validation passed - remove validating tag, add validated, resume
                    await _mark_validated(client, torrent)
                    validated_count += 1
                    print(f"Validation passed: {torrent.name} - {report.message}")

                    # Update download history status
                    await conn.execute(
                        """
                        UPDATE download_history
                        SET status = 'downloading', updated_at = NOW()
                        WHERE torrent_hash = $1 AND status = 'downloading'
                        """,
                        torrent.hash,
                    )
                    await write_validation_state(torrent.hash, STEP_PASSED, report)
                    try:
                        from app.services.seeding import apply_seeding_limits
                        from app.services.media_profile import MediaProfile

                        mp = MediaProfile.from_row(profile) if profile else None
                        await apply_seeding_limits(client, torrent.hash, mp)
                    except Exception as e:
                        print(f"Could not apply seeding limits: {e}")
                else:
                    # Validation failed - execute failure action
                    await _handle_validation_failure(client, conn, torrent, report, failure_action, media_type)
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


async def _handle_validation_failure(client, conn, torrent, report, failure_action: str, media_type: str):
    """Handle failed validation based on configured action."""

    # Remove validating tag
    await client.remove_tags(torrent.hash, ["validating"])

    if failure_action == "delete":
        # Delete torrent and files
        await client.delete_torrent(torrent.hash, delete_files=True)

        # Update download history
        await conn.execute(
            """
            UPDATE download_history
            SET status = 'validation_failed', error_message = $1, updated_at = NOW()
            WHERE torrent_hash = $2
            """,
            report.message,
            torrent.hash,
        )

        # Update media status back to wanted
        await _reset_media_status(conn, torrent.tags, media_type)

        print(f"Torrent deleted due to validation failure: {torrent.name}")

    elif failure_action == "quarantine":
        # Add quarantine tag and set quarantine category
        await client.set_tags(torrent.hash, ["validation-failed", "quarantine"])

        # Try to set quarantine category (may not exist)
        try:
            await client.set_category(torrent.hash, "quarantine")
        except Exception:
            pass  # Category may not exist

        # Update download history
        await conn.execute(
            """
            UPDATE download_history
            SET status = 'quarantined', error_message = $1, updated_at = NOW()
            WHERE torrent_hash = $2
            """,
            report.message,
            torrent.hash,
        )

        print(f"Torrent quarantined: {torrent.name}")

    else:  # pause_notify (default)
        # Keep paused, add failure tag
        await client.set_tags(torrent.hash, ["validation-failed"])

        # Update download history
        await conn.execute(
            """
            UPDATE download_history
            SET status = 'validation_failed', error_message = $1, updated_at = NOW()
            WHERE torrent_hash = $2
            """,
            report.message,
            torrent.hash,
        )

        print(f"Torrent paused due to validation failure: {torrent.name}")


async def _reset_media_status(conn, tags: list, media_type: str):
    """Reset media item status back to wanted after validation failure with delete action."""
    if not tags:
        return

    media_id = None
    for tag in tags:
        if tag.startswith(f"{media_type}-"):
            try:
                media_id = int(tag.split("-")[1])
                break
            except ValueError, IndexError:
                continue

    if not media_id:
        return

    table_name = {
        "movie": "movies",
        "show": "shows",
        "anime": "anime",
        "album": "albums",
    }.get(media_type)

    if table_name:
        await conn.execute(f"UPDATE {table_name} SET status = 'wanted', updated_at = NOW() WHERE id = $1", media_id)


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


async def _get_profile_for_torrent(conn, torrent, media_type: str) -> dict:
    """Get the media profile for a torrent based on its associated media item."""
    if not torrent.tags:
        return None

    media_id = None
    for tag in torrent.tags:
        if tag.startswith(f"{media_type}-"):
            try:
                media_id = int(tag.split("-")[1])
                break
            except ValueError, IndexError:
                continue

    if not media_id:
        return None

    # Get profile ID from media table
    table_name = {
        "movie": "movies",
        "show": "shows",
        "anime": "anime",
        "album": "albums",
    }.get(media_type, "movies")

    media = await conn.fetchrow(f"SELECT media_profile_id FROM {table_name} WHERE id = $1", media_id)

    if not media or not media.get("media_profile_id"):
        return None

    profile = await conn.fetchrow("SELECT * FROM media_profiles WHERE id = $1", media["media_profile_id"])

    return dict(profile) if profile else None
