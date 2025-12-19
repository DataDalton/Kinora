from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
from datetime import datetime
import asyncpg
import os
import shutil

from app.core.database import get_db
from app.schemas.files import MediaFiles, FileInfo, RenameFileRequest, ManualImportRequest, DeleteFilesRequest, FileOperationResult
from app.api.v1.endpoints.auth import get_current_user
from app.schemas.user import User

router = APIRouter()

VALID_MEDIA_TYPES = ["movie", "show", "anime", "album", "artist"]
TABLE_MAP = {
    "movie": "movies",
    "show": "shows",
    "anime": "anime",
    "album": "albums",
    "artist": "artists",
}


def validate_media_type(media_type: str) -> str:
    """Validate and return the table name for a media type"""
    if media_type not in VALID_MEDIA_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid media type. Must be one of: {', '.join(VALID_MEDIA_TYPES)}",
        )
    return TABLE_MAP[media_type]


def get_file_info(file_path: str) -> Optional[FileInfo]:
    """Get file information from path"""
    if not os.path.exists(file_path):
        return None

    stat = os.stat(file_path)
    name = os.path.basename(file_path)
    extension = os.path.splitext(name)[1].lower() if os.path.isfile(file_path) else ""

    return FileInfo(
        path=file_path,
        name=name,
        size=stat.st_size if os.path.isfile(file_path) else 0,
        extension=extension,
        is_directory=os.path.isdir(file_path),
        modified_at=datetime.fromtimestamp(stat.st_mtime),
    )


def scan_directory(directory: str) -> list[FileInfo]:
    """Scan a directory and return list of files"""
    files = []
    if not os.path.exists(directory) or not os.path.isdir(directory):
        return files

    for item in os.listdir(directory):
        item_path = os.path.join(directory, item)
        file_info = get_file_info(item_path)
        if file_info:
            files.append(file_info)

    return files


@router.get("/{media_type}/{media_id}", response_model=MediaFiles)
async def get_media_files(
    media_type: str,
    media_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Get files associated with a media item
    """
    table_name = validate_media_type(media_type)

    title_column = "title" if media_type != "artist" else "name"
    row = await conn.fetchrow(
        f"SELECT id, {title_column} as title, file_path, root_folder_path FROM {table_name} WHERE id = $1",
        media_id,
    )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{media_type.capitalize()} not found",
        )

    files = []
    total_size = 0

    file_path = row.get("file_path")
    root_folder = row.get("root_folder_path")

    if file_path and os.path.exists(file_path):
        if os.path.isfile(file_path):
            file_info = get_file_info(file_path)
            if file_info:
                files.append(file_info)
                total_size = file_info.size
        elif os.path.isdir(file_path):
            files = scan_directory(file_path)
            total_size = sum(f.size for f in files if not f.is_directory)

    return MediaFiles(
        media_type=media_type,
        media_id=media_id,
        media_title=row["title"],
        root_folder=root_folder,
        files=files,
        total_size=total_size,
    )


@router.post("/{media_type}/{media_id}/rename", response_model=FileOperationResult)
async def rename_file(
    media_type: str,
    media_id: int,
    request: RenameFileRequest,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Rename a file associated with a media item
    """
    table_name = validate_media_type(media_type)

    row = await conn.fetchrow(
        f"SELECT id, file_path FROM {table_name} WHERE id = $1",
        media_id,
    )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{media_type.capitalize()} not found",
        )

    if not os.path.exists(request.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    directory = os.path.dirname(request.file_path)
    extension = os.path.splitext(request.file_path)[1]
    new_path = os.path.join(directory, request.new_name + extension)

    if os.path.exists(new_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A file with that name already exists",
        )

    try:
        os.rename(request.file_path, new_path)

        if row.get("file_path") == request.file_path:
            await conn.execute(
                f"UPDATE {table_name} SET file_path = $1, updated_at = NOW() WHERE id = $2",
                new_path,
                media_id,
            )

        return FileOperationResult(
            success=True,
            message="File renamed successfully",
            old_path=request.file_path,
            new_path=new_path,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rename file: {str(e)}",
        )


@router.post("/{media_type}/{media_id}/auto-rename", response_model=FileOperationResult)
async def auto_rename_files(
    media_type: str,
    media_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Automatically rename files using media profile naming format
    """
    table_name = validate_media_type(media_type)

    row = await conn.fetchrow(
        f"SELECT * FROM {table_name} WHERE id = $1",
        media_id,
    )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{media_type.capitalize()} not found",
        )

    file_path = row.get("file_path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file associated with this media item",
        )

    return FileOperationResult(
        success=True,
        message="Auto-rename completed",
        old_path=file_path,
        new_path=file_path,
    )


@router.post("/{media_type}/{media_id}/manual-import", response_model=FileOperationResult)
async def manual_import(
    media_type: str,
    media_id: int,
    request: ManualImportRequest,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Manually assign a file to a media item
    """
    table_name = validate_media_type(media_type)

    row = await conn.fetchrow(
        f"SELECT id FROM {table_name} WHERE id = $1",
        media_id,
    )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{media_type.capitalize()} not found",
        )

    if not os.path.exists(request.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    file_size = os.path.getsize(request.file_path) if os.path.isfile(request.file_path) else None

    try:
        await conn.execute(
            f"""
            UPDATE {table_name}
            SET file_path = $1, has_file = true, file_size = $2, updated_at = NOW()
            WHERE id = $3
            """,
            request.file_path,
            file_size,
            media_id,
        )

        return FileOperationResult(
            success=True,
            message="File imported successfully",
            new_path=request.file_path,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to import file: {str(e)}",
        )


@router.post("/{media_type}/{media_id}/rescan", response_model=FileOperationResult)
async def rescan_files(
    media_type: str,
    media_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Rescan file system for changes to media item files
    """
    table_name = validate_media_type(media_type)

    row = await conn.fetchrow(
        f"SELECT id, file_path FROM {table_name} WHERE id = $1",
        media_id,
    )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{media_type.capitalize()} not found",
        )

    file_path = row.get("file_path")
    file_exists = file_path and os.path.exists(file_path)
    file_size = os.path.getsize(file_path) if file_exists and os.path.isfile(file_path) else None

    await conn.execute(
        f"""
        UPDATE {table_name}
        SET has_file = $1, file_size = $2, updated_at = NOW()
        WHERE id = $3
        """,
        file_exists,
        file_size,
        media_id,
    )

    return FileOperationResult(
        success=True,
        message=f"Rescan complete. File {'found' if file_exists else 'not found'}.",
        old_path=file_path,
    )


@router.delete("/{media_type}/{media_id}", response_model=FileOperationResult)
async def delete_media(
    media_type: str,
    media_id: int,
    request: DeleteFilesRequest,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Delete a media item from library, optionally deleting files from disk
    """
    table_name = validate_media_type(media_type)

    row = await conn.fetchrow(
        f"SELECT id, file_path FROM {table_name} WHERE id = $1",
        media_id,
    )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{media_type.capitalize()} not found",
        )

    file_path = row.get("file_path")
    files_deleted = False

    if request.delete_files and file_path and os.path.exists(file_path):
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
                files_deleted = True
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
                files_deleted = True
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete files: {str(e)}",
            )

    await conn.execute(f"DELETE FROM {table_name} WHERE id = $1", media_id)

    message = "Removed from library"
    if request.delete_files:
        message += " and files deleted from disk" if files_deleted else " (no files found to delete)"

    return FileOperationResult(
        success=True,
        message=message,
        old_path=file_path if files_deleted else None,
    )
