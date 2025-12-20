"""
Torrent Validation Service

Validates torrent file contents against media profile settings
before allowing download to proceed.
"""

from typing import List, Dict, Any, Optional, TYPE_CHECKING
from dataclasses import dataclass
from enum import Enum
import os
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
        '.exe', '.bat', '.cmd', '.sh', '.msi', '.dll', '.scr',
        '.com', '.ps1', '.vbs', '.js', '.jar', '.pif'
    ]

    # Default allowed by media type
    DEFAULT_ALLOWED = {
        'movie': ['.mkv', '.mp4', '.avi', '.m4v', '.mov', '.wmv', '.flv', '.webm', '.ts'],
        'show': ['.mkv', '.mp4', '.avi', '.m4v', '.mov', '.wmv', '.flv', '.webm', '.ts'],
        'anime': ['.mkv', '.mp4', '.avi', '.m4v'],
        'album': ['.flac', '.mp3', '.m4a', '.aac', '.ogg', '.opus', '.wav', '.wma'],
        'music': ['.flac', '.mp3', '.m4a', '.aac', '.ogg', '.opus', '.wav', '.wma'],
    }

    # Common non-media files to ignore (not forbidden, just not counted as valid)
    IGNORED_EXTENSIONS = [
        '.nfo', '.txt', '.srt', '.sub', '.idx', '.ass', '.ssa',
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.sfv', '.cue',
        '.log', '.m3u', '.pls', '.md5', '.sha1', '.sha256'
    ]

    def validate_files(
        self,
        files: List[Dict[str, Any]],
        media_type: str,
        allowed_extensions: Optional[List[str]] = None,
        forbidden_extensions: Optional[List[str]] = None,
    ) -> ValidationReport:
        """
        Validate torrent files against extension rules.

        Args:
            files: List of file dicts from qBittorrent (with 'name' and 'size' keys)
            media_type: Type of media ('movie', 'show', 'anime', 'album')
            allowed_extensions: List of allowed file extensions (with dot)
            forbidden_extensions: List of forbidden extensions (with dot)

        Returns:
            ValidationReport with detailed results
        """
        # Use defaults if not specified
        if allowed_extensions is None:
            allowed_extensions = self.DEFAULT_ALLOWED.get(media_type, [])
        if forbidden_extensions is None:
            forbidden_extensions = self.DEFAULT_FORBIDDEN

        # Normalize extensions to lowercase with leading dot
        allowed = set(
            ext.lower() if ext.startswith('.') else f'.{ext.lower()}'
            for ext in allowed_extensions
        )
        forbidden = set(
            ext.lower() if ext.startswith('.') else f'.{ext.lower()}'
            for ext in forbidden_extensions
        )
        ignored = set(self.IGNORED_EXTENSIONS)

        valid_files = []
        invalid_files = []
        forbidden_files = []
        valid_size = 0
        total_size = 0

        for file_info in files:
            file_name = file_info.get('name', '')
            file_size = file_info.get('size', 0)
            total_size += file_size

            # Get file extension
            _, ext = os.path.splitext(file_name.lower())

            # Check forbidden first (security)
            if ext in forbidden:
                forbidden_files.append(file_name)
                continue

            # Check if allowed
            if ext in allowed:
                valid_files.append(file_name)
                valid_size += file_size
            elif ext not in ignored:
                # Not allowed and not in ignore list
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
        if hasattr(torrent_info, 'state'):
            state_str = str(torrent_info.state.value if hasattr(torrent_info.state, 'value') else torrent_info.state)
            if 'meta' in state_str.lower():
                return False

        # Size of 0 usually means metadata not yet received
        if hasattr(torrent_info, 'size') and torrent_info.size == 0:
            return False

        return True


# Global instance
torrent_validator = TorrentValidator()


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
        return ValidationReport(
            result=ValidationResult.PASSED,
            valid_files=[],
            invalid_files=[],
            forbidden_files=[],
            total_files=0,
            valid_size=0,
            total_size=0,
            message="Validation skipped (disabled in profile)"
        )

    # Wait for metadata to be ready
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
        return ValidationReport(
            result=ValidationResult.PENDING,
            valid_files=[],
            invalid_files=[],
            forbidden_files=[],
            total_files=0,
            valid_size=0,
            total_size=0,
            message=f"Metadata not available after {metadata_timeout}s timeout"
        )

    # Get file list and validate
    files = await client.get_torrent_files(torrent_hash)
    if not files:
        logger.warning(f"No files found in torrent {torrent_hash[:8]}")
        return ValidationReport(
            result=ValidationResult.PENDING,
            valid_files=[],
            invalid_files=[],
            forbidden_files=[],
            total_files=0,
            valid_size=0,
            total_size=0,
            message="No files found in torrent"
        )

    # Get allowed/forbidden extensions from profile
    allowed_extensions = profile.get_allowed_extensions_for_type(media_type)
    forbidden_extensions = profile.forbidden_extensions or validator.DEFAULT_FORBIDDEN

    # Run validation
    report = validator.validate_files(
        files=files,
        media_type=media_type,
        allowed_extensions=allowed_extensions,
        forbidden_extensions=forbidden_extensions,
    )

    # Handle result
    if report.result == ValidationResult.PASSED:
        await _mark_validated_and_resume(client, torrent_hash)
        logger.info(f"Validation passed for {torrent_hash[:8]}: {report.message}")
    else:
        await _handle_validation_failure(client, torrent_hash, profile, report)
        logger.warning(f"Validation failed for {torrent_hash[:8]}: {report.message}")

    return report


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

    except Exception as e:
        logger.error(f"Failed to handle validation failure for {torrent_hash[:8]}: {e}")
