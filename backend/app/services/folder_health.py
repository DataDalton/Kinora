"""
Folder health monitoring service for checking root folder accessibility and disk space.
Provides health checks and status updates for all configured root folders.
"""
import os
import tempfile
import uuid
import shutil
from typing import Optional, Tuple, List, Dict, Any
from datetime import datetime
import asyncpg

from app.core.cache import cacheGet, cacheSet
from app.services.folder_selector import folderSelector


HEALTH_CHECK_CACHE_TTL = 300  # 5 minutes cache for health status


class FolderHealthMonitor:
    """
    Service for monitoring the health of root folders.
    Checks: accessibility, read/write permissions, disk space thresholds.
    """

    async def checkFolderHealth(
        self,
        folder: Dict[str, Any]
    ) -> Tuple[str, Optional[str]]:
        """
        Check folder accessibility and health.
        Returns (status, message) where status is 'healthy', 'warning', or 'error'.
        """
        rootPath = folder.get("root_path")
        downloadPath = folder.get("download_path")

        if not rootPath:
            return "error", "Root path is not configured"

        # Check root path accessibility
        rootAccessible, rootError = self._testPathAccessibility(rootPath)
        if not rootAccessible:
            return "error", f"Root path inaccessible: {rootError}"

        # Check root path write permissions
        rootWritable, writeError = self._testWriteAccess(rootPath)
        if not rootWritable:
            return "error", f"Root path not writable: {writeError}"

        # Check download path if configured
        if downloadPath:
            downloadAccessible, downloadError = self._testPathAccessibility(downloadPath)
            if not downloadAccessible:
                return "error", f"Download path inaccessible: {downloadError}"

            downloadWritable, downloadWriteError = self._testWriteAccess(downloadPath)
            if not downloadWritable:
                return "error", f"Download path not writable: {downloadWriteError}"

            # Verify same filesystem for hardlinks
            if not folderSelector.validateSameFilesystem(rootPath, downloadPath):
                return "error", "Root and download paths are on different filesystems (hardlinks will fail)"

        # Check disk space thresholds
        warningMessage = self._checkDiskSpaceWarning(folder)
        if warningMessage:
            return "warning", warningMessage

        return "healthy", None

    async def checkAllFolders(
        self,
        conn: asyncpg.Connection
    ) -> List[Dict[str, Any]]:
        """Check health of all active folders and update their status."""
        rows = await conn.fetch(
            """
            SELECT id, media_type, name, root_path, download_path, priority,
                   fill_threshold_percent, fill_threshold_gb, is_active, is_default,
                   total_space_bytes, free_space_bytes, last_health_check,
                   health_status, health_message
            FROM root_folders
            WHERE is_active = true
            """
        )

        results = []
        for row in rows:
            folder = dict(row)

            # Update disk space first
            await folderSelector.updateFolderDiskSpace(folder)

            # Check health
            status, message = await self.checkFolderHealth(folder)

            # Update in database
            await self.updateFolderHealth(conn, folder["id"], status, message)

            folder["health_status"] = status
            folder["health_message"] = message
            folder["last_health_check"] = datetime.utcnow()
            results.append(folder)

        return results

    async def updateFolderHealth(
        self,
        conn: asyncpg.Connection,
        folderId: int,
        status: str,
        message: Optional[str]
    ) -> None:
        """Update folder health status in database."""
        await conn.execute(
            """
            UPDATE root_folders
            SET health_status = $1, health_message = $2, last_health_check = now()
            WHERE id = $3
            """,
            status, message, folderId
        )

    async def getHealthSummary(
        self,
        conn: asyncpg.Connection
    ) -> Dict[str, int]:
        """Get summary counts of folder health statuses."""
        row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE health_status = 'healthy') as healthy,
                COUNT(*) FILTER (WHERE health_status = 'warning') as warning,
                COUNT(*) FILTER (WHERE health_status = 'error') as error,
                COUNT(*) FILTER (WHERE health_status = 'unknown') as unknown
            FROM root_folders
            WHERE is_active = true
            """
        )
        return dict(row)

    async def getDriveStats(
        self,
        conn: asyncpg.Connection
    ) -> List[Dict[str, Any]]:
        """Get disk space statistics grouped by drive/mount point."""
        rows = await conn.fetch(
            """
            SELECT id, media_type, name, root_path, download_path,
                   priority, fill_threshold_percent, fill_threshold_gb,
                   is_active, total_space_bytes, free_space_bytes,
                   last_health_check, health_status, health_message,
                   created_at, updated_at
            FROM root_folders
            WHERE is_active = true
            ORDER BY root_path
            """
        )

        # Group folders by drive/mount point
        driveMap: Dict[str, Dict[str, Any]] = {}

        for row in rows:
            folder = dict(row)
            rootPath = folder["root_path"]

            # Extract drive/mount point
            drive = self._extractDrive(rootPath)

            if drive not in driveMap:
                # Get drive-level disk space
                totalBytes, freeBytes = folderSelector.getDiskSpace(rootPath)
                usedBytes = (totalBytes - freeBytes) if totalBytes and freeBytes else 0
                usedPercent = (usedBytes / totalBytes * 100) if totalBytes else 0

                driveMap[drive] = {
                    "drive": drive,
                    "total_bytes": totalBytes or 0,
                    "used_bytes": usedBytes,
                    "free_bytes": freeBytes or 0,
                    "used_percent": round(usedPercent, 2),
                    "folder_count": 0,
                    "folders": []
                }

            # Add folder to drive
            driveMap[drive]["folder_count"] += 1

            # Add computed stats to folder
            if folder["total_space_bytes"] and folder["free_space_bytes"]:
                folder["used_space_bytes"] = folder["total_space_bytes"] - folder["free_space_bytes"]
                folder["used_percent"] = round(
                    (folder["used_space_bytes"] / folder["total_space_bytes"]) * 100, 2
                )
            else:
                folder["used_space_bytes"] = None
                folder["used_percent"] = None

            driveMap[drive]["folders"].append(folder)

        return list(driveMap.values())

    def _extractDrive(self, path: str) -> str:
        """Extract drive letter or mount point from path."""
        import platform

        if platform.system() == "Windows":
            # Return drive letter (e.g., "C:", "D:")
            drive = os.path.splitdrive(path)[0]
            return drive.upper() if drive else path
        else:
            # Return mount point (first two path components or root)
            parts = path.split(os.sep)
            if len(parts) >= 3 and parts[1] in ("mnt", "media", "home"):
                return os.sep.join(parts[:3])
            elif len(parts) >= 2:
                return os.sep.join(parts[:2])
            return "/"

    def _testPathAccessibility(self, path: str) -> Tuple[bool, Optional[str]]:
        """Test if a path is accessible."""
        try:
            if not os.path.exists(path):
                return False, "Path does not exist"

            if not os.path.isdir(path):
                return False, "Path is not a directory"

            # Try to list directory contents
            os.listdir(path)
            return True, None

        except PermissionError:
            return False, "Permission denied"
        except OSError as e:
            return False, str(e)

    def _testWriteAccess(self, path: str) -> Tuple[bool, Optional[str]]:
        """Test if a path is writable by creating and deleting a temp file."""
        try:
            # Create a temporary file
            testFileName = f".health_check_{uuid.uuid4().hex}"
            testFilePath = os.path.join(path, testFileName)

            # Write test
            with open(testFilePath, "w") as f:
                f.write("health_check")

            # Read test
            with open(testFilePath, "r") as f:
                content = f.read()

            # Delete test file
            os.remove(testFilePath)

            if content != "health_check":
                return False, "Read/write verification failed"

            return True, None

        except PermissionError:
            return False, "Permission denied"
        except OSError as e:
            return False, str(e)

    def _testHardlinkSupport(self, rootPath: str, downloadPath: str) -> Tuple[bool, Optional[str]]:
        """Test if hardlinks can be created between root and download paths."""
        try:
            # Create a test file in download path
            testFileName = f".hardlink_test_{uuid.uuid4().hex}"
            sourceFile = os.path.join(downloadPath, testFileName)
            targetFile = os.path.join(rootPath, testFileName)

            # Create source file
            with open(sourceFile, "w") as f:
                f.write("hardlink_test")

            # Try to create hardlink
            os.link(sourceFile, targetFile)

            # Verify hardlink
            sourceStat = os.stat(sourceFile)
            targetStat = os.stat(targetFile)

            # Check inode match (hardlink verification)
            success = sourceStat.st_ino == targetStat.st_ino

            # Cleanup
            os.remove(sourceFile)
            os.remove(targetFile)

            if not success:
                return False, "Hardlink inode verification failed"

            return True, None

        except PermissionError:
            return False, "Permission denied"
        except OSError as e:
            if "cross-device" in str(e).lower():
                return False, "Cross-filesystem hardlinks not supported"
            return False, str(e)

    def _checkDiskSpaceWarning(self, folder: Dict[str, Any]) -> Optional[str]:
        """Check if folder is approaching its fill threshold."""
        totalBytes = folder.get("total_space_bytes")
        freeBytes = folder.get("free_space_bytes")
        thresholdPercent = folder.get("fill_threshold_percent")
        thresholdGb = folder.get("fill_threshold_gb")

        if totalBytes is None or freeBytes is None:
            return None

        usedBytes = totalBytes - freeBytes
        usedPercent = (usedBytes / totalBytes) * 100
        freeGb = freeBytes / (1024 ** 3)

        # Check if approaching thresholds (within 10% or 50GB)
        if thresholdPercent is not None:
            if usedPercent >= thresholdPercent:
                return f"Disk usage ({usedPercent:.1f}%) has reached threshold ({thresholdPercent}%)"
            elif usedPercent >= thresholdPercent - 10:
                return f"Disk usage ({usedPercent:.1f}%) is approaching threshold ({thresholdPercent}%)"

        if thresholdGb is not None:
            if freeGb < thresholdGb:
                return f"Free space ({freeGb:.1f} GB) is below threshold ({thresholdGb} GB)"
            elif freeGb < thresholdGb + 50:
                return f"Free space ({freeGb:.1f} GB) is approaching threshold ({thresholdGb} GB)"

        # General low space warning (less than 10GB free)
        if freeGb < 10:
            return f"Low disk space: only {freeGb:.1f} GB remaining"

        return None

    async def testFolder(
        self,
        rootPath: str,
        downloadPath: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Test a folder configuration before saving.
        Returns detailed test results.
        """
        result = {
            "success": True,
            "root_path_accessible": False,
            "root_path_writable": False,
            "download_path_accessible": False,
            "download_path_writable": False,
            "same_filesystem": False,
            "hardlink_supported": False,
            "message": None
        }

        # Test root path
        rootAccessible, rootError = self._testPathAccessibility(rootPath)
        result["root_path_accessible"] = rootAccessible
        if not rootAccessible:
            result["success"] = False
            result["message"] = f"Root path: {rootError}"
            return result

        rootWritable, writeError = self._testWriteAccess(rootPath)
        result["root_path_writable"] = rootWritable
        if not rootWritable:
            result["success"] = False
            result["message"] = f"Root path not writable: {writeError}"
            return result

        # Test download path if provided
        if downloadPath:
            # Create download path if it doesn't exist
            try:
                os.makedirs(downloadPath, exist_ok=True)
            except OSError as e:
                result["success"] = False
                result["message"] = f"Cannot create download path: {e}"
                return result

            downloadAccessible, downloadError = self._testPathAccessibility(downloadPath)
            result["download_path_accessible"] = downloadAccessible
            if not downloadAccessible:
                result["success"] = False
                result["message"] = f"Download path: {downloadError}"
                return result

            downloadWritable, downloadWriteError = self._testWriteAccess(downloadPath)
            result["download_path_writable"] = downloadWritable
            if not downloadWritable:
                result["success"] = False
                result["message"] = f"Download path not writable: {downloadWriteError}"
                return result

            # Test same filesystem
            sameFs = folderSelector.validateSameFilesystem(rootPath, downloadPath)
            result["same_filesystem"] = sameFs
            if not sameFs:
                result["success"] = False
                result["message"] = "Root and download paths are on different filesystems (hardlinks will not work)"
                return result

            # Test hardlink support
            hardlinkOk, hardlinkError = self._testHardlinkSupport(rootPath, downloadPath)
            result["hardlink_supported"] = hardlinkOk
            if not hardlinkOk:
                result["success"] = False
                result["message"] = f"Hardlink test failed: {hardlinkError}"
                return result
        else:
            # No download path, mark as N/A
            result["download_path_accessible"] = True
            result["download_path_writable"] = True
            result["same_filesystem"] = True
            result["hardlink_supported"] = True

        result["message"] = "All tests passed"
        return result


# Singleton instance
folderHealthMonitor = FolderHealthMonitor()
