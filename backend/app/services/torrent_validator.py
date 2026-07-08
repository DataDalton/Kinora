"""
Torrent Validation Service

Validates torrent file contents against media profile settings
before allowing download to proceed.
"""

from typing import List, Dict, Any, Optional, TYPE_CHECKING
from dataclasses import dataclass
from enum import Enum
import os
import json
import asyncio
import logging

if TYPE_CHECKING:
    from app.services.download_clients.qbittorrent import QBittorrentClient
    from app.services.media_profile import MediaProfile

logger = logging.getLogger(__name__)


class ValidationResult(str, Enum):
    """Validation result status"""

    PASSED = "passed"
    FAILED_FORBIDDEN = "failed_forbidden"
    FAILED_NO_VALID = "failed_no_valid"
    PENDING = "pending"


@dataclass
class ValidationReport:
    """Detailed validation report"""

    result: ValidationResult
    valid_files: List[str]
    invalid_files: List[str]
    forbidden_files: List[str]
    total_files: int
    valid_size: int
    total_size: int
    message: str


class TorrentValidator:
    """
    Validates torrent files against media profile extension rules.

    Validation logic:
    1. Check each file extension against forbidden list (instant fail)
    2. Check if any files match allowed extensions
    3. If no allowed files found, validation fails
    """

    # Default forbidden extensions (security risk)
    DEFAULT_FORBIDDEN = [
        ".exe",
        ".bat",
        ".cmd",
        ".sh",
        ".msi",
        ".dll",
        ".scr",
        ".com",
        ".ps1",
        ".vbs",
        ".js",
        ".jar",
        ".pif",
    ]

    # Default allowed by media type
    DEFAULT_ALLOWED = {
        "movie": [".mkv", ".mp4", ".avi", ".m4v", ".mov", ".wmv", ".flv", ".webm", ".ts"],
        "show": [".mkv", ".mp4", ".avi", ".m4v", ".mov", ".wmv", ".flv", ".webm", ".ts"],
        "anime": [".mkv", ".mp4", ".avi", ".m4v"],
        "album": [".flac", ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".wma"],
        "music": [".flac", ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".wma"],
    }

    # Common non-media files to ignore (not forbidden, just not counted as valid)
    IGNORED_EXTENSIONS = [
        ".nfo",
        ".txt",
        ".srt",
        ".sub",
        ".idx",
        ".ass",
        ".ssa",
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".bmp",
        ".sfv",
        ".cue",
        ".log",
        ".m3u",
        ".pls",
        ".md5",
        ".sha1",
        ".sha256",
    ]

    def validate_files(
        self,
        files: List[Dict[str, Any]],
        media_type: str,
        allowed_extensions: Optional[List[str]] = None,
        forbidden_extensions: Optional[List[str]] = None,
        mode: str = "allowlist",
    ) -> ValidationReport:
        """
        Validate torrent files against extension rules.

        Args:
            files: List of file dicts from qBittorrent (with 'name' and 'size' keys)
            media_type: Type of media ('movie', 'show', 'anime', 'album')
            allowed_extensions: List of allowed file extensions (with dot)
            forbidden_extensions: List of forbidden extensions (with dot)
            mode: 'allowlist' accepts only allowed_extensions; 'blocklist' accepts
                every file except forbidden_extensions.

        Returns:
            ValidationReport with detailed results
        """
        # Use defaults if not specified
        if allowed_extensions is None:
            allowed_extensions = self.DEFAULT_ALLOWED.get(media_type, [])
        if forbidden_extensions is None:
            forbidden_extensions = self.DEFAULT_FORBIDDEN

        # Normalize extensions to lowercase with leading dot
        allowed = set(ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in allowed_extensions)
        forbidden = set(ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in forbidden_extensions)
        ignored = set(self.IGNORED_EXTENSIONS)

        valid_files = []
        invalid_files = []
        forbidden_files = []
        valid_size = 0
        total_size = 0

        for file_info in files:
            file_name = file_info.get("name", "")
            file_size = file_info.get("size", 0)
            total_size += file_size

            # Get file extension
            _, ext = os.path.splitext(file_name.lower())

            # Forbidden extensions are always rejected, in both modes.
            if ext in forbidden:
                forbidden_files.append(file_name)
                continue

            if mode == "blocklist":
                # Accept every file that is not forbidden or ignored.
                if ext not in ignored:
                    valid_files.append(file_name)
                    valid_size += file_size
            else:
                # allowlist: only extensions in the allowed set are accepted.
                if ext in allowed:
                    valid_files.append(file_name)
                    valid_size += file_size
                elif ext not in ignored:
                    invalid_files.append(file_name)

        # Determine result
        if forbidden_files:
            result = ValidationResult.FAILED_FORBIDDEN
            message = f"Forbidden files detected: {', '.join(os.path.basename(f) for f in forbidden_files[:3])}"
            if len(forbidden_files) > 3:
                message += f" and {len(forbidden_files) - 3} more"
        elif not valid_files:
            result = ValidationResult.FAILED_NO_VALID
            message = f"No valid media files found. Expected: {', '.join(allowed_extensions[:5])}"
        else:
            result = ValidationResult.PASSED
            valid_size_mb = valid_size / 1024 / 1024
            message = f"Validation passed: {len(valid_files)} valid file(s) ({valid_size_mb:.1f} MB)"

        return ValidationReport(
            result=result,
            valid_files=valid_files,
            invalid_files=invalid_files,
            forbidden_files=forbidden_files,
            total_files=len(files),
            valid_size=valid_size,
            total_size=total_size,
            message=message,
        )

    def is_metadata_ready(self, torrent_info: Any) -> bool:
        """
        Check if torrent metadata is ready (file list available).

        A torrent needs metadata before we can validate its files.
        Metadata is ready when the torrent has a size > 0 and state is not "metaDL".

        Args:
            torrent_info: TorrentInfo object from qBittorrent client

        Returns:
            True if metadata is ready, False otherwise
        """
        if not torrent_info:
            return False

        # qBittorrent uses "metaDL" state while fetching metadata
        if hasattr(torrent_info, "state"):
            state_str = str(torrent_info.state.value if hasattr(torrent_info.state, "value") else torrent_info.state)
            if "meta" in state_str.lower():
                return False

        # Size of 0 usually means metadata not yet received
        if hasattr(torrent_info, "size") and torrent_info.size == 0:
            return False

        return True


# Global instance
torrent_validator = TorrentValidator()


# Validation step identifiers persisted to download_history.validation_step and
# pushed to the frontend for live progress display.
STEP_WAITING_METADATA = "waiting_metadata"
STEP_DETECTING_FILES = "detecting_files"
STEP_CHECKING_EXTENSIONS = "checking_extensions"
STEP_RESOLVING = "resolving"
STEP_PASSED = "passed"
STEP_FAILED = "failed"
STEP_PENDING = "pending"


def report_to_dict(report: ValidationReport) -> Dict[str, Any]:
    """Serialize a ValidationReport into a JSON-compatible dict."""
    result = report.result.value if hasattr(report.result, "value") else report.result
    return {
        "result": result,
        "valid_files": report.valid_files,
        "invalid_files": report.invalid_files,
        "forbidden_files": report.forbidden_files,
        "total_files": report.total_files,
        "valid_size": report.valid_size,
        "total_size": report.total_size,
        "message": report.message,
    }


async def write_validation_state(
    torrent_hash: str,
    step: str,
    report: Optional[ValidationReport] = None,
) -> None:
    """
    Persist the current validation step (and optional report) to download_history
    and push it to connected users over the WebSocket.

    A missing history row is not an error: manual or not-yet-recorded torrents
    simply skip persistence but still emit the live update.
    """
    report_json = report_to_dict(report) if report is not None else None
    try:
        from app.db import get_pool

        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE download_history
                SET validation_step = $1,
                    validation_report = $2::jsonb,
                    updated_at = NOW()
                WHERE torrent_hash = $3
                """,
                step,
                # Passed directly: the pool's jsonb codec encodes the dict, whereas
                # json.dumps here would store a double-encoded JSON string.
                report_json,
                torrent_hash,
            )
    except Exception as e:
        logger.debug(f"Could not persist validation state for {torrent_hash[:8]}: {e}")

    try:
        from app.core.webtransport import webtransport_manager

        for user_id in webtransport_manager.get_active_users():
            await webtransport_manager.send_validation_update(user_id, torrent_hash, step, report_json)
    except Exception as e:
        logger.debug(f"Could not push validation update for {torrent_hash[:8]}: {e}")


async def validate_and_resume_torrent(
    torrent_hash: str,
    client: "QBittorrentClient",
    profile: "MediaProfile",
    media_type: str,
    metadata_timeout: float = 30.0,
    poll_interval: float = 1.0,
) -> ValidationReport:
    """
    Wait for torrent metadata, validate files, and resume or handle failure.

    Called immediately after adding a torrent to make validation event-driven
    rather than relying on periodic polling.

    Args:
        torrent_hash: Hash of the torrent to validate
        client: qBittorrent client instance
        profile: MediaProfile with validation settings
        media_type: Type of media ('movie', 'show', 'anime', 'album')
        metadata_timeout: Max seconds to wait for metadata
        poll_interval: Seconds between metadata checks

    Returns:
        ValidationReport with results
    """
    validator = TorrentValidator()

    # Skip validation if disabled in profile
    if not profile.validation_enabled:
        logger.info(f"Validation disabled for profile '{profile.name}', resuming torrent {torrent_hash[:8]}")
        await _mark_validated_and_resume(client, torrent_hash)
        await _apply_seeding(client, torrent_hash, profile)
        skip_report = ValidationReport(
            result=ValidationResult.PASSED,
            valid_files=[],
            invalid_files=[],
            forbidden_files=[],
            total_files=0,
            valid_size=0,
            total_size=0,
            message="Validation skipped (disabled in profile)",
        )
        await write_validation_state(torrent_hash, STEP_PASSED, skip_report)
        return skip_report

    # Wait for metadata to be ready
    await write_validation_state(torrent_hash, STEP_WAITING_METADATA)
    elapsed = 0.0
    torrent_info = None
    while elapsed < metadata_timeout:
        torrent_info = await client.get_torrent(torrent_hash)
        if torrent_info and validator.is_metadata_ready(torrent_info):
            break
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

    if not torrent_info or not validator.is_metadata_ready(torrent_info):
        logger.warning(f"Metadata timeout for torrent {torrent_hash[:8]} after {metadata_timeout}s")
        # Keep torrent paused with validating tag for manual review
        pending_report = ValidationReport(
            result=ValidationResult.PENDING,
            valid_files=[],
            invalid_files=[],
            forbidden_files=[],
            total_files=0,
            valid_size=0,
            total_size=0,
            message=f"Metadata not available after {metadata_timeout}s timeout",
        )
        await write_validation_state(torrent_hash, STEP_PENDING, pending_report)
        return pending_report

    # Get file list and validate
    await write_validation_state(torrent_hash, STEP_DETECTING_FILES)
    files = await client.get_torrent_files(torrent_hash)
    if not files:
        logger.warning(f"No files found in torrent {torrent_hash[:8]}")
        no_files_report = ValidationReport(
            result=ValidationResult.PENDING,
            valid_files=[],
            invalid_files=[],
            forbidden_files=[],
            total_files=0,
            valid_size=0,
            total_size=0,
            message="No files found in torrent",
        )
        await write_validation_state(torrent_hash, STEP_PENDING, no_files_report)
        return no_files_report

    # Get allowed/forbidden extensions from profile
    allowed_extensions = profile.get_allowed_extensions_for_type(media_type)
    forbidden_extensions = profile.forbidden_extensions or validator.DEFAULT_FORBIDDEN

    # Run validation
    await write_validation_state(torrent_hash, STEP_CHECKING_EXTENSIONS)
    report = validator.validate_files(
        files=files,
        media_type=media_type,
        allowed_extensions=allowed_extensions,
        forbidden_extensions=forbidden_extensions,
        mode=profile.validation_mode,
    )

    # Handle result
    await write_validation_state(torrent_hash, STEP_RESOLVING, report)
    if report.result == ValidationResult.PASSED:
        await _mark_validated_and_resume(client, torrent_hash)
        await _apply_seeding(client, torrent_hash, profile)
        logger.info(f"Validation passed for {torrent_hash[:8]}: {report.message}")
        await write_validation_state(torrent_hash, STEP_PASSED, report)
    else:
        await _handle_validation_failure(client, torrent_hash, profile, report)
        logger.warning(f"Validation failed for {torrent_hash[:8]}: {report.message}")
        await write_validation_state(torrent_hash, STEP_FAILED, report)

    return report


async def _apply_seeding(client: "QBittorrentClient", torrent_hash: str, profile: "MediaProfile") -> None:
    """Apply the resolved seeding limits after a torrent is resumed."""
    try:
        from app.services.seeding import apply_seeding_limits

        await apply_seeding_limits(client, torrent_hash, profile)
    except Exception as e:
        logger.debug(f"Could not apply seeding limits for {torrent_hash[:8]}: {e}")


async def _mark_validated_and_resume(client: "QBittorrentClient", torrent_hash: str) -> None:
    """Remove validating tag, add validated tag, and resume torrent."""
    try:
        await client.remove_tags(torrent_hash, ["validating"])
        await client.set_tags(torrent_hash, ["validated"])
        await client.resume_torrent(torrent_hash)
    except Exception as e:
        logger.error(f"Failed to mark torrent {torrent_hash[:8]} as validated: {e}")


async def _handle_validation_failure(
    client: "QBittorrentClient",
    torrent_hash: str,
    profile: "MediaProfile",
    report: ValidationReport,
) -> None:
    """Handle validation failure based on profile settings."""
    action = profile.validation_failure_action

    try:
        await client.remove_tags(torrent_hash, ["validating"])

        if action == "delete":
            logger.info(f"Deleting torrent {torrent_hash[:8]} due to validation failure")
            await client.delete_torrent(torrent_hash, delete_files=True)

        elif action == "quarantine":
            logger.info(f"Quarantining torrent {torrent_hash[:8]} due to validation failure")
            await client.set_tags(torrent_hash, ["validation-failed", "quarantine"])
            await client.set_category(torrent_hash, "quarantine")

        else:  # pause_notify (default)
            logger.info(f"Pausing torrent {torrent_hash[:8]} for manual review: {report.message}")
            await client.set_tags(torrent_hash, ["validation-failed"])
            # Torrent is already paused, just leave it

        # Notify the user of the failed validation and the action taken.
        try:
            from app.services.notifications import create_notification

            action_label = {
                "delete": "deleted",
                "quarantine": "quarantined",
            }.get(action, "paused for review")
            await create_notification(
                type="validation_failed",
                title="Torrent validation failed",
                message=f"{report.message}. Torrent was {action_label}.",
                severity="warning",
                data={"torrent_hash": torrent_hash, "action": action},
            )
        except Exception as notify_error:
            logger.debug(f"Validation-failure notification failed: {notify_error}")

    except Exception as e:
        logger.error(f"Failed to handle validation failure for {torrent_hash[:8]}: {e}")
