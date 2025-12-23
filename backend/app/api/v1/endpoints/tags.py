from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
import asyncpg

from app.db import get_db
from app.db.repositories import TagRepository, MediaTagRepository
from app.schemas.tags import Tag, TagCreate, TagUpdate, MediaTagCreate, MediaTagResponse, BulkTagUpdate
from app.api.v1.endpoints.auth import get_current_user
from app.schemas.user import User

router = APIRouter()

VALID_MEDIA_TYPES = ["movie", "show", "anime", "album", "artist"]


def validateMediaType(mediaType: str) -> None:
    """Validate media type is allowed."""
    if mediaType not in VALID_MEDIA_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid media type. Must be one of: {', '.join(VALID_MEDIA_TYPES)}",
        )


@router.get("/", response_model=List[Tag])
async def get_tags(
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Get all tags."""
    repo = TagRepository(conn)
    rows = await repo.list()
    return [Tag(**row) for row in rows]


@router.get("/{tag_id}", response_model=Tag)
async def get_tag(
    tag_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Get a specific tag by ID."""
    repo = TagRepository(conn)
    tag = await repo.getById(tag_id)

    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found",
        )

    return Tag(**tag)


@router.post("/", response_model=Tag, status_code=status.HTTP_201_CREATED)
async def create_tag(
    tag_data: TagCreate,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Create a new tag."""
    repo = TagRepository(conn)

    # Check for duplicate name (case-insensitive)
    existing = await conn.fetchrow(
        "SELECT id FROM tags WHERE LOWER(name) = LOWER($1)", tag_data.name
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tag with this name already exists",
        )

    tag = await repo.create(tag_data.name, tag_data.color)
    return Tag(**tag)


@router.put("/{tag_id}", response_model=Tag)
async def update_tag(
    tag_id: int,
    tag_data: TagUpdate,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Update a tag."""
    repo = TagRepository(conn)

    existing = await repo.getById(tag_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found",
        )

    # Check for name conflict if name is being changed
    if tag_data.name:
        nameExists = await conn.fetchrow(
            "SELECT id FROM tags WHERE LOWER(name) = LOWER($1) AND id != $2",
            tag_data.name,
            tag_id,
        )
        if nameExists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tag with this name already exists",
            )

    updated = await repo.update(tag_id, tag_data.name, tag_data.color)
    return Tag(**updated)


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
    tag_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Delete a tag (also removes from all media items via cascade)."""
    repo = TagRepository(conn)

    existing = await repo.getById(tag_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found",
        )

    await repo.delete(tag_id)
    return None


@router.get("/media/{media_type}/{media_id}", response_model=List[Tag])
async def get_media_tags(
    media_type: str,
    media_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Get all tags for a specific media item."""
    validateMediaType(media_type)

    repo = MediaTagRepository(conn)
    rows = await repo.getTagsForMedia(media_type, media_id)
    return [Tag(**row) for row in rows]


@router.post("/media/{media_type}/{media_id}", response_model=List[Tag])
async def set_media_tags(
    media_type: str,
    media_id: int,
    tag_data: MediaTagCreate,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Set tags for a media item (replaces existing tags)."""
    validateMediaType(media_type)

    tagRepo = TagRepository(conn)
    mediaTagRepo = MediaTagRepository(conn)

    # Validate all tags exist
    for tagId in tag_data.tag_ids:
        if not await tagRepo.getById(tagId):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tag with id {tagId} not found",
            )

    async with conn.transaction():
        await mediaTagRepo.setTags(media_type, media_id, tag_data.tag_ids)

    rows = await mediaTagRepo.getTagsForMedia(media_type, media_id)
    return [Tag(**row) for row in rows]


@router.post("/media/{media_type}/{media_id}/add/{tag_id}", response_model=List[Tag])
async def add_tag_to_media(
    media_type: str,
    media_id: int,
    tag_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Add a single tag to a media item."""
    validateMediaType(media_type)

    tagRepo = TagRepository(conn)
    mediaTagRepo = MediaTagRepository(conn)

    if not await tagRepo.getById(tag_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found",
        )

    await mediaTagRepo.addTag(media_type, media_id, tag_id)
    rows = await mediaTagRepo.getTagsForMedia(media_type, media_id)
    return [Tag(**row) for row in rows]


@router.delete("/media/{media_type}/{media_id}/remove/{tag_id}", response_model=List[Tag])
async def remove_tag_from_media(
    media_type: str,
    media_id: int,
    tag_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Remove a single tag from a media item."""
    validateMediaType(media_type)

    mediaTagRepo = MediaTagRepository(conn)
    await mediaTagRepo.removeTag(media_type, media_id, tag_id)
    rows = await mediaTagRepo.getTagsForMedia(media_type, media_id)
    return [Tag(**row) for row in rows]


@router.delete("/media/{media_type}/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
async def clear_media_tags(
    media_type: str,
    media_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Remove all tags from a media item."""
    validateMediaType(media_type)

    repo = MediaTagRepository(conn)
    await repo.removeAllFromMedia(media_type, media_id)
    return None


@router.post("/bulk/{media_type}", response_model=dict)
async def bulk_update_tags(
    media_type: str,
    bulk_data: BulkTagUpdate,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Bulk add/remove tags from multiple media items using batch operations."""
    validateMediaType(media_type)

    if not bulk_data.add_tags and not bulk_data.remove_tags:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must specify at least one tag to add or remove",
        )

    tagRepo = TagRepository(conn)
    mediaTagRepo = MediaTagRepository(conn)

    # Validate tags to add exist
    for tagId in bulk_data.add_tags:
        if not await tagRepo.getById(tagId):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tag with id {tagId} not found",
            )

    addedCount = 0
    removedCount = 0

    async with conn.transaction():
        # Batch remove operations (single query per tag instead of N queries)
        for tagId in bulk_data.remove_tags:
            removed = await mediaTagRepo.removeTagsBatch(media_type, bulk_data.media_ids, tagId)
            removedCount += removed

        # Batch add operations (single query per tag instead of N queries)
        for tagId in bulk_data.add_tags:
            added = await mediaTagRepo.addTagsBatch(media_type, bulk_data.media_ids, tagId)
            addedCount += added

    return {
        "success": True,
        "added": addedCount,
        "removed": removedCount,
        "media_count": len(bulk_data.media_ids),
    }


@router.get("/filter/{media_type}", response_model=List[int])
async def get_media_by_tag(
    media_type: str,
    tag_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Get all media IDs that have a specific tag."""
    validateMediaType(media_type)

    repo = MediaTagRepository(conn)
    rows = await repo.getMediaForTag(tag_id, media_type)
    return [row["media_id"] for row in rows]
