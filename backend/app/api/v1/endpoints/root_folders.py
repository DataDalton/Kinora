"""
API endpoints for managing root folders and folder selection settings.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
import asyncpg
import os
import platform

from app.db import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.schemas.root_folder import (
    RootFolderCreate,
    RootFolderUpdate,
    RootFolderResponse,
    RootFolderWithStats,
    FolderSelectionSettingsUpdate,
    FolderSelectionSettingsResponse,
    FolderTestRequest,
    FolderTestResponse,
    DriveStats,
    FolderHealthSummary,
    BrowseDirectoryRequest,
    BrowseDirectoryResponse,
)
from app.services.folder_selector import folderSelector
from app.services.folder_health import folderHealthMonitor
from app.tasks.folder_health import checkSingleFolder

router = APIRouter()


@router.get("/", response_model=List[RootFolderWithStats])
async def listRootFolders(
    mediaType: Optional[str] = Query(None, description="Filter by media type"),
    conn: asyncpg.Connection = Depends(get_db),
    currentUser=Depends(get_current_user),
):
    """List all root folders, optionally filtered by media type."""
    if mediaType:
        folders = await folderSelector.getFoldersForMediaType(conn, mediaType, activeOnly=False)
    else:
        rows = await conn.fetch(
            """
            SELECT id, media_type, name, root_path, download_path, priority,
                   fill_threshold_percent, fill_threshold_gb, is_active, is_default,
                   total_space_bytes, free_space_bytes, last_health_check,
                   health_status, health_message, created_at, updated_at
            FROM root_folders
            ORDER BY media_type, priority ASC, id ASC
            """
        )
        folders = [dict(row) for row in rows]

    # Add computed stats
    result = []
    for folder in folders:
        total = folder.get("total_space_bytes")
        free = folder.get("free_space_bytes")
        if total and free:
            folder["used_space_bytes"] = total - free
            folder["used_percent"] = round(((total - free) / total) * 100, 2)
        else:
            folder["used_space_bytes"] = None
            folder["used_percent"] = None
        result.append(folder)

    return result


@router.get("/health", response_model=FolderHealthSummary)
async def getFolderHealthSummary(
    conn: asyncpg.Connection = Depends(get_db),
    currentUser=Depends(get_current_user),
):
    """Get summary of folder health statuses."""
    summary = await folderHealthMonitor.getHealthSummary(conn)
    return FolderHealthSummary(
        total_folders=summary["total"],
        healthy_count=summary["healthy"],
        warning_count=summary["warning"],
        error_count=summary["error"],
        unknown_count=summary["unknown"],
    )


@router.get("/drives", response_model=List[DriveStats])
async def getDriveStatistics(
    conn: asyncpg.Connection = Depends(get_db),
    currentUser=Depends(get_current_user),
):
    """Get disk space statistics grouped by drive/mount point."""
    driveStats = await folderHealthMonitor.getDriveStats(conn)
    return driveStats


@router.get("/selection-settings/{mediaType}", response_model=FolderSelectionSettingsResponse)
async def getSelectionSettings(
    mediaType: str,
    conn: asyncpg.Connection = Depends(get_db),
    currentUser=Depends(get_current_user),
):
    """Get folder selection settings for a media type."""
    row = await conn.fetchrow(
        """
        SELECT id, media_type, selection_mode, created_at, updated_at
        FROM folder_selection_settings
        WHERE media_type = $1
        """,
        mediaType
    )

    if not row:
        # Return default settings
        return FolderSelectionSettingsResponse(
            id=0,
            media_type=mediaType,
            selection_mode="most_free_space",
            created_at=None,
            updated_at=None,
        )

    return dict(row)


@router.put("/selection-settings/{mediaType}", response_model=FolderSelectionSettingsResponse)
async def updateSelectionSettings(
    mediaType: str,
    settings: FolderSelectionSettingsUpdate,
    conn: asyncpg.Connection = Depends(get_db),
    currentUser=Depends(get_current_user),
):
    """Update folder selection settings for a media type."""
    if currentUser.role != 'administrator':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can update settings",
        )

    await folderSelector.setSelectionMode(conn, mediaType, settings.selection_mode)

    row = await conn.fetchrow(
        """
        SELECT id, media_type, selection_mode, created_at, updated_at
        FROM folder_selection_settings
        WHERE media_type = $1
        """,
        mediaType
    )

    return dict(row)


@router.get("/{folderId}", response_model=RootFolderWithStats)
async def getRootFolder(
    folderId: int,
    conn: asyncpg.Connection = Depends(get_db),
    currentUser=Depends(get_current_user),
):
    """Get a specific root folder by ID."""
    folder = await folderSelector.getFolder(conn, folderId)
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Root folder not found",
        )

    # Add computed stats
    total = folder.get("total_space_bytes")
    free = folder.get("free_space_bytes")
    if total and free:
        folder["used_space_bytes"] = total - free
        folder["used_percent"] = round(((total - free) / total) * 100, 2)
    else:
        folder["used_space_bytes"] = None
        folder["used_percent"] = None

    return folder


@router.post("/", response_model=RootFolderWithStats, status_code=status.HTTP_201_CREATED)
async def createRootFolder(
    folderData: RootFolderCreate,
    conn: asyncpg.Connection = Depends(get_db),
    currentUser=Depends(get_current_user),
):
    """
    Create a new root folder.
    Auto-generates download_path if not provided.
    Validates same filesystem for hardlink support.
    Creates directories if they don't exist.
    """
    if currentUser.role != 'administrator':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can create root folders",
        )

    try:
        folder = await folderSelector.createFolder(
            conn,
            mediaType=folderData.media_type,
            name=folderData.name,
            rootPath=folderData.root_path,
            downloadPath=folderData.download_path,
            priority=folderData.priority,
            fillThresholdPercent=folderData.fill_threshold_percent,
            fillThresholdGb=folderData.fill_threshold_gb,
        )

        # Add computed stats
        total = folder.get("total_space_bytes")
        free = folder.get("free_space_bytes")
        if total and free:
            folder["used_space_bytes"] = total - free
            folder["used_percent"] = round(((total - free) / total) * 100, 2)
        else:
            folder["used_space_bytes"] = None
            folder["used_percent"] = None

        return folder

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create folder: {str(e)}",
        )


@router.put("/{folderId}", response_model=RootFolderWithStats)
async def updateRootFolder(
    folderId: int,
    folderData: RootFolderUpdate,
    conn: asyncpg.Connection = Depends(get_db),
    currentUser=Depends(get_current_user),
):
    """Update an existing root folder."""
    if currentUser.role != 'administrator':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can update root folders",
        )

    try:
        folder = await folderSelector.updateFolder(
            conn,
            folderId,
            name=folderData.name,
            rootPath=folderData.root_path,
            downloadPath=folderData.download_path,
            priority=folderData.priority,
            fillThresholdPercent=folderData.fill_threshold_percent,
            fillThresholdGb=folderData.fill_threshold_gb,
            isActive=folderData.is_active,
        )

        if not folder:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Root folder not found",
            )

        # Add computed stats
        total = folder.get("total_space_bytes")
        free = folder.get("free_space_bytes")
        if total and free:
            folder["used_space_bytes"] = total - free
            folder["used_percent"] = round(((total - free) / total) * 100, 2)
        else:
            folder["used_space_bytes"] = None
            folder["used_percent"] = None

        return folder

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete("/{folderId}", status_code=status.HTTP_204_NO_CONTENT)
async def deleteRootFolder(
    folderId: int,
    conn: asyncpg.Connection = Depends(get_db),
    currentUser=Depends(get_current_user),
):
    """
    Delete a root folder.
    Fails if media items are assigned to this folder.
    """
    if currentUser.role != 'administrator':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can delete root folders",
        )

    try:
        deleted = await folderSelector.deleteFolder(conn, folderId)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Root folder not found",
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/{folderId}/test", response_model=FolderTestResponse)
async def testRootFolder(
    folderId: int,
    conn: asyncpg.Connection = Depends(get_db),
    currentUser=Depends(get_current_user),
):
    """Test folder accessibility and hardlink support."""
    folder = await folderSelector.getFolder(conn, folderId)
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Root folder not found",
        )

    result = await folderHealthMonitor.testFolder(
        folder["root_path"],
        folder["download_path"]
    )

    return result


@router.post("/test", response_model=FolderTestResponse)
async def testFolderPaths(
    testData: FolderTestRequest,
    currentUser=Depends(get_current_user),
):
    """Test folder paths before creating a folder."""
    result = await folderHealthMonitor.testFolder(
        testData.root_path,
        testData.download_path
    )
    return result


@router.post("/{folderId}/refresh-health")
async def refreshFolderHealth(
    folderId: int,
    conn: asyncpg.Connection = Depends(get_db),
    currentUser=Depends(get_current_user),
):
    """Manually trigger a health check for a specific folder."""
    folder = await folderSelector.getFolder(conn, folderId)
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Root folder not found",
        )

    # Trigger async health check
    checkSingleFolder.delay(folderId)

    return {"success": True, "message": "Health check started"}


@router.post("/browse", response_model=BrowseDirectoryResponse)
async def browseDirectory(
    browseData: BrowseDirectoryRequest,
    currentUser=Depends(get_current_user),
):
    """Browse filesystem directories for folder selection."""
    if currentUser.role != 'administrator':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can browse directories",
        )

    path = browseData.path

    # Handle root/initial request
    if not path:
        if platform.system() == "Windows":
            # Return available drives on Windows
            import string
            drives = []
            for letter in string.ascii_uppercase:
                drivePath = f"{letter}:\\"
                if os.path.exists(drivePath):
                    drives.append(drivePath)
            return BrowseDirectoryResponse(
                path="",
                parent=None,
                directories=drives,
                is_root=True,
            )
        else:
            # Start from root on Unix
            path = "/"

    # Normalize path
    path = os.path.normpath(path)

    if not os.path.exists(path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Path does not exist",
        )

    if not os.path.isdir(path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path is not a directory",
        )

    try:
        entries = os.listdir(path)
        directories = []

        for entry in sorted(entries):
            if entry.startswith("."):
                continue  # Skip hidden files/folders
            fullPath = os.path.join(path, entry)
            try:
                if os.path.isdir(fullPath):
                    directories.append(entry)
            except (PermissionError, OSError):
                continue

        # Determine parent
        if platform.system() == "Windows":
            parent = os.path.dirname(path)
            isRoot = len(path) <= 3  # e.g., "C:\"
            if isRoot:
                parent = None
        else:
            parent = os.path.dirname(path) if path != "/" else None
            isRoot = path == "/"

        return BrowseDirectoryResponse(
            path=path,
            parent=parent,
            directories=directories,
            is_root=isRoot,
        )

    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied to access this directory",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
