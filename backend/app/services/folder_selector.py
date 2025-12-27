"""
Folder selection service for choosing the appropriate root folder based on configured rules.
Handles disk space caching and filesystem validation for hardlink support.
"""
import os
import platform
import shutil
from typing import Optional, Tuple, List, Dict, Any
from datetime import datetime
import asyncpg

from app.core.cache import cacheGet, cacheSet, cacheDelete


DISK_SPACE_CACHE_TTL = 60  # 1 minute cache for disk space


class FolderSelector:
    """
    Service for selecting root folders based on configured selection modes.
    Supports: most_free_space, priority, fill_threshold
    """

    async def getFoldersForMediaType(
        self,
        conn: asyncpg.Connection,
        mediaType: str,
        activeOnly: bool = True
    ) -> List[Dict[str, Any]]:
        """Get all root folders for a media type, ordered by priority."""
        query = """
            SELECT id, media_type, name, root_path, download_path, priority,
                   fill_threshold_percent, fill_threshold_gb, is_active, is_default,
                   total_space_bytes, free_space_bytes, last_health_check,
                   health_status, health_message, created_at, updated_at
            FROM root_folders
            WHERE media_type = $1
        """
        if activeOnly:
            query += " AND is_active = true"
        query += " ORDER BY priority ASC, id ASC"

        rows = await conn.fetch(query, mediaType)
        return [dict(row) for row in rows]

    async def getFolder(
        self,
        conn: asyncpg.Connection,
        folderId: int
    ) -> Optional[Dict[str, Any]]:
        """Get a single root folder by ID."""
        row = await conn.fetchrow(
            """
            SELECT id, media_type, name, root_path, download_path, priority,
                   fill_threshold_percent, fill_threshold_gb, is_active, is_default,
                   total_space_bytes, free_space_bytes, last_health_check,
                   health_status, health_message, created_at, updated_at
            FROM root_folders
            WHERE id = $1
            """,
            folderId
        )
        return dict(row) if row else None

    async def getDefaultFolder(
        self,
        conn: asyncpg.Connection,
        mediaType: str
    ) -> Optional[Dict[str, Any]]:
        """Get the default folder for a media type."""
        row = await conn.fetchrow(
            """
            SELECT id, media_type, name, root_path, download_path, priority,
                   fill_threshold_percent, fill_threshold_gb, is_active, is_default,
                   total_space_bytes, free_space_bytes, last_health_check,
                   health_status, health_message, created_at, updated_at
            FROM root_folders
            WHERE media_type = $1 AND is_default = true AND is_active = true
            """,
            mediaType
        )
        return dict(row) if row else None

    async def selectFolder(
        self,
        conn: asyncpg.Connection,
        mediaType: str,
        overrideFolderId: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Select the best folder for a media type based on configured selection mode.
        If overrideFolderId is provided, use that folder directly.
        """
        # Use override if provided
        if overrideFolderId:
            folder = await self.getFolder(conn, overrideFolderId)
            if folder and folder["is_active"]:
                return folder

        # Get all active folders for this media type
        folders = await self.getFoldersForMediaType(conn, mediaType, activeOnly=True)
        if not folders:
            return None

        # Get selection mode
        selectionMode = await self.getSelectionMode(conn, mediaType)

        # Update disk space for all folders
        for folder in folders:
            await self.updateFolderDiskSpace(folder)

        # Apply selection logic
        if selectionMode == "most_free_space":
            return await self._selectMostFreeSpace(folders)
        elif selectionMode == "priority":
            return await self._selectByPriority(folders)
        elif selectionMode == "fill_threshold":
            return await self._selectByFillThreshold(folders)
        else:
            # Default to most free space
            return await self._selectMostFreeSpace(folders)

    async def getSelectionMode(
        self,
        conn: asyncpg.Connection,
        mediaType: str
    ) -> str:
        """Get the selection mode for a media type."""
        row = await conn.fetchrow(
            "SELECT selection_mode FROM folder_selection_settings WHERE media_type = $1",
            mediaType
        )
        return row["selection_mode"] if row else "most_free_space"

    async def setSelectionMode(
        self,
        conn: asyncpg.Connection,
        mediaType: str,
        selectionMode: str
    ) -> None:
        """Set the selection mode for a media type."""
        await conn.execute(
            """
            INSERT INTO folder_selection_settings (media_type, selection_mode)
            VALUES ($1, $2)
            ON CONFLICT (media_type)
            DO UPDATE SET selection_mode = $2, updated_at = now()
            """,
            mediaType, selectionMode
        )

    async def _selectMostFreeSpace(
        self,
        folders: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Select the folder with the most free space."""
        if not folders:
            return None

        # Filter to healthy folders only
        healthyFolders = [f for f in folders if f.get("health_status") != "error"]
        if not healthyFolders:
            healthyFolders = folders  # Fallback to all if none healthy

        # Sort by free space descending
        sortedFolders = sorted(
            healthyFolders,
            key=lambda f: f.get("free_space_bytes") or 0,
            reverse=True
        )
        return sortedFolders[0] if sortedFolders else None

    async def _selectByPriority(
        self,
        folders: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Select folders in priority order.
        Move to next priority when current folder exceeds threshold.
        """
        if not folders:
            return None

        # Folders are already sorted by priority
        for folder in folders:
            if folder.get("health_status") == "error":
                continue

            # Check if folder is usable (under threshold)
            if self._isFolderUsable(folder):
                return folder

        # If all are over threshold, return highest priority healthy folder
        for folder in folders:
            if folder.get("health_status") != "error":
                return folder

        return folders[0] if folders else None

    async def _selectByFillThreshold(
        self,
        folders: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Fill each folder until threshold, then move to next.
        Similar to priority but strictly follows threshold rules.
        """
        return await self._selectByPriority(folders)

    def _isFolderUsable(self, folder: Dict[str, Any]) -> bool:
        """Check if folder is under its fill threshold."""
        totalBytes = folder.get("total_space_bytes")
        freeBytes = folder.get("free_space_bytes")
        thresholdPercent = folder.get("fill_threshold_percent")
        thresholdGb = folder.get("fill_threshold_gb")

        if totalBytes is None or freeBytes is None:
            return True  # Can't determine, assume usable

        # Check percentage threshold
        if thresholdPercent is not None:
            usedPercent = ((totalBytes - freeBytes) / totalBytes) * 100
            if usedPercent >= thresholdPercent:
                return False

        # Check GB threshold
        if thresholdGb is not None:
            freeGb = freeBytes / (1024 ** 3)
            if freeGb < thresholdGb:
                return False

        return True

    async def updateFolderDiskSpace(self, folder: Dict[str, Any]) -> None:
        """Update folder's disk space values from cache or filesystem."""
        rootPath = folder.get("root_path")
        if not rootPath:
            return

        cacheKey = f"disk_space:{rootPath}"
        cached = await cacheGet(cacheKey)

        if cached:
            folder["total_space_bytes"] = cached.get("total")
            folder["free_space_bytes"] = cached.get("free")
        else:
            total, free = self.getDiskSpace(rootPath)
            folder["total_space_bytes"] = total
            folder["free_space_bytes"] = free

            if total is not None:
                await cacheSet(cacheKey, {"total": total, "free": free}, DISK_SPACE_CACHE_TTL)

    def getDiskSpace(self, path: str) -> Tuple[Optional[int], Optional[int]]:
        """Get disk space for a path. Returns (total_bytes, free_bytes)."""
        try:
            if not os.path.exists(path):
                return None, None

            usage = shutil.disk_usage(path)
            return usage.total, usage.free
        except (OSError, PermissionError):
            return None, None

    def validateSameFilesystem(self, rootPath: str, downloadPath: str) -> bool:
        """
        Verify that root_path and download_path are on the same filesystem.
        This is required for hardlinks to work.
        """
        if platform.system() == "Windows":
            # On Windows, check if drive letters match
            rootDrive = os.path.splitdrive(rootPath)[0].upper()
            downloadDrive = os.path.splitdrive(downloadPath)[0].upper()
            return rootDrive == downloadDrive
        else:
            # On Unix, check if device IDs match
            try:
                if not os.path.exists(rootPath):
                    os.makedirs(rootPath, exist_ok=True)
                if not os.path.exists(downloadPath):
                    os.makedirs(downloadPath, exist_ok=True)

                rootStat = os.stat(rootPath)
                downloadStat = os.stat(downloadPath)
                return rootStat.st_dev == downloadStat.st_dev
            except (OSError, PermissionError):
                return False

    def generateDownloadPath(self, rootPath: str, mediaType: str) -> str:
        """
        Auto-generate a download path on the same drive/filesystem as root_path.
        Creates a Downloads folder at the same level as the root path.
        """
        if platform.system() == "Windows":
            # Get drive letter and create Downloads folder on same drive
            drive = os.path.splitdrive(rootPath)[0]
            if drive:
                return os.path.join(drive, "Downloads", mediaType)
            else:
                # Network path or similar
                parent = os.path.dirname(rootPath)
                return os.path.join(parent, "Downloads", mediaType)
        else:
            # Unix: create Downloads folder at parent level of root
            parent = os.path.dirname(rootPath.rstrip("/"))
            return os.path.join(parent, "downloads", mediaType)

    async def createFolder(
        self,
        conn: asyncpg.Connection,
        mediaType: str,
        name: str,
        rootPath: str,
        downloadPath: Optional[str] = None,
        priority: int = 0,
        fillThresholdPercent: Optional[int] = None,
        fillThresholdGb: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create a new root folder."""
        # Auto-generate download path if not provided
        if not downloadPath:
            downloadPath = self.generateDownloadPath(rootPath, mediaType)

        # Validate same filesystem
        if not self.validateSameFilesystem(rootPath, downloadPath):
            raise ValueError(
                f"Download path must be on the same filesystem as root path for hardlinks to work. "
                f"Root: {rootPath}, Download: {downloadPath}"
            )

        # Create directories if they don't exist
        os.makedirs(rootPath, exist_ok=True)
        os.makedirs(downloadPath, exist_ok=True)

        # Get initial disk space
        totalBytes, freeBytes = self.getDiskSpace(rootPath)

        # Insert folder
        row = await conn.fetchrow(
            """
            INSERT INTO root_folders (
                media_type, name, root_path, download_path, priority,
                fill_threshold_percent, fill_threshold_gb,
                total_space_bytes, free_space_bytes, health_status
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'unknown')
            RETURNING *
            """,
            mediaType, name, rootPath, downloadPath, priority,
            fillThresholdPercent, fillThresholdGb,
            totalBytes, freeBytes
        )

        return dict(row)

    async def updateFolder(
        self,
        conn: asyncpg.Connection,
        folderId: int,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Update an existing root folder."""
        folder = await self.getFolder(conn, folderId)
        if not folder:
            return None

        # Build update query dynamically
        updates = []
        values = []
        paramIdx = 1

        fieldMap = {
            "name": "name",
            "rootPath": "root_path",
            "downloadPath": "download_path",
            "priority": "priority",
            "fillThresholdPercent": "fill_threshold_percent",
            "fillThresholdGb": "fill_threshold_gb",
            "isActive": "is_active",
        }

        for pyField, dbField in fieldMap.items():
            if pyField in kwargs and kwargs[pyField] is not None:
                updates.append(f"{dbField} = ${paramIdx}")
                values.append(kwargs[pyField])
                paramIdx += 1

        if not updates:
            return folder

        # Validate filesystem if paths changed
        # Use existing folder paths if new paths are None or not provided
        newRootPath = kwargs.get("rootPath") if kwargs.get("rootPath") is not None else folder["root_path"]
        newDownloadPath = kwargs.get("downloadPath") if kwargs.get("downloadPath") is not None else folder["download_path"]

        if newRootPath != folder["root_path"] or newDownloadPath != folder["download_path"]:
            if not self.validateSameFilesystem(newRootPath, newDownloadPath):
                raise ValueError(
                    "Download path must be on the same filesystem as root path for hardlinks to work."
                )

        updates.append(f"updated_at = ${paramIdx}")
        values.append(datetime.utcnow())
        paramIdx += 1

        values.append(folderId)
        query = f"UPDATE root_folders SET {', '.join(updates)} WHERE id = ${paramIdx} RETURNING *"

        row = await conn.fetchrow(query, *values)
        return dict(row) if row else None

    async def deleteFolder(
        self,
        conn: asyncpg.Connection,
        folderId: int
    ) -> bool:
        """Delete a root folder. Fails if media items are assigned to it."""
        # Check if any media items are using this folder
        mediaTypes = [
            ("movies", "root_folder_id"),
            ("shows", "root_folder_id"),
            ("anime", "root_folder_id"),
            ("artists", "root_folder_id"),
            ("albums", "root_folder_id"),
        ]

        for table, column in mediaTypes:
            count = await conn.fetchval(
                f"SELECT COUNT(*) FROM {table} WHERE {column} = $1",
                folderId
            )
            if count > 0:
                raise ValueError(
                    f"Cannot delete folder: {count} items in {table} are assigned to it. "
                    "Reassign or delete them first."
                )

        result = await conn.execute(
            "DELETE FROM root_folders WHERE id = $1",
            folderId
        )
        return result == "DELETE 1"

    async def updateDiskSpaceCache(
        self,
        conn: asyncpg.Connection,
        folderId: int
    ) -> None:
        """Update the cached disk space values in the database."""
        folder = await self.getFolder(conn, folderId)
        if not folder:
            return

        rootPath = folder["root_path"]
        totalBytes, freeBytes = self.getDiskSpace(rootPath)

        await conn.execute(
            """
            UPDATE root_folders
            SET total_space_bytes = $1, free_space_bytes = $2, updated_at = now()
            WHERE id = $3
            """,
            totalBytes, freeBytes, folderId
        )

        # Also update Redis cache
        cacheKey = f"disk_space:{rootPath}"
        if totalBytes is not None:
            await cacheSet(cacheKey, {"total": totalBytes, "free": freeBytes}, DISK_SPACE_CACHE_TTL)


# Singleton instance
folderSelector = FolderSelector()
