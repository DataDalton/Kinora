from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
import asyncpg

from app.core.database import get_db
from app.schemas.tags import Tag, TagCreate, TagUpdate, MediaTagCreate, MediaTagResponse, BulkTagUpdate
from app.api.v1.endpoints.auth import get_current_user
from app.schemas.user import User

router = APIRouter()


@router.get("/", response_model=List[Tag])
async def get_tags(
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Get all tags
    """
    rows = await conn.fetch("SELECT * FROM tags ORDER BY name ASC")
    return [Tag(**dict(row)) for row in rows]


@router.get("/{tag_id}", response_model=Tag)
async def get_tag(
    tag_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Get a specific tag by ID
    """
    row = await conn.fetchrow("SELECT * FROM tags WHERE id = $1", tag_id)

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found",
        )

    return Tag(**dict(row))


@router.post("/", response_model=Tag, status_code=status.HTTP_201_CREATED)
async def create_tag(
    tag_data: TagCreate,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Create a new tag
    """
    existing = await conn.fetchrow(
        "SELECT id FROM tags WHERE LOWER(name) = LOWER($1)", tag_data.name
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tag with this name already exists",
        )

    row = await conn.fetchrow(
        """
        INSERT INTO tags (name, color)
        VALUES ($1, $2)
        RETURNING *
        """,
        tag_data.name,
        tag_data.color,
    )

    return Tag(**dict(row))


@router.put("/{tag_id}", response_model=Tag)
async def update_tag(
    tag_id: int,
    tag_data: TagUpdate,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Update a tag
    """
    existing = await conn.fetchrow("SELECT * FROM tags WHERE id = $1", tag_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found",
        )

    if tag_data.name:
        name_exists = await conn.fetchrow(
            "SELECT id FROM tags WHERE LOWER(name) = LOWER($1) AND id != $2",
            tag_data.name,
            tag_id,
        )
        if name_exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tag with this name already exists",
            )

    update_fields = []
    values = []
    param_count = 1

    if tag_data.name is not None:
        update_fields.append(f"name = ${param_count}")
        values.append(tag_data.name)
        param_count += 1

    if tag_data.color is not None:
        update_fields.append(f"color = ${param_count}")
        values.append(tag_data.color)
        param_count += 1

    if not update_fields:
        return Tag(**dict(existing))

    values.append(tag_id)
    query = f"""
        UPDATE tags SET {", ".join(update_fields)}
        WHERE id = ${param_count}
        RETURNING *
    """

    row = await conn.fetchrow(query, *values)
    return Tag(**dict(row))


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
    tag_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Delete a tag (also removes from all media items)
    """
    existing = await conn.fetchrow("SELECT id FROM tags WHERE id = $1", tag_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found",
        )

    await conn.execute("DELETE FROM tags WHERE id = $1", tag_id)
    return None


@router.get("/media/{media_type}/{media_id}", response_model=List[Tag])
async def get_media_tags(
    media_type: str,
    media_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Get all tags for a specific media item
    """
    valid_types = ["movie", "show", "anime", "album", "artist"]
    if media_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid media type. Must be one of: {', '.join(valid_types)}",
        )

    rows = await conn.fetch(
        """
        SELECT t.* FROM tags t
        INNER JOIN media_tags mt ON t.id = mt.tag_id
        WHERE mt.media_type = $1 AND mt.media_id = $2
        ORDER BY t.name ASC
        """,
        media_type,
        media_id,
    )
    return [Tag(**dict(row)) for row in rows]


@router.post("/media/{media_type}/{media_id}", response_model=List[Tag])
async def set_media_tags(
    media_type: str,
    media_id: int,
    tag_data: MediaTagCreate,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Set tags for a media item (replaces existing tags)
    """
    valid_types = ["movie", "show", "anime", "album", "artist"]
    if media_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid media type. Must be one of: {', '.join(valid_types)}",
        )

    async with conn.transaction():
        await conn.execute(
            "DELETE FROM media_tags WHERE media_type = $1 AND media_id = $2",
            media_type,
            media_id,
        )

        for tag_id in tag_data.tag_ids:
            tag_exists = await conn.fetchrow("SELECT id FROM tags WHERE id = $1", tag_id)
            if not tag_exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Tag with id {tag_id} not found",
                )

            await conn.execute(
                """
                INSERT INTO media_tags (tag_id, media_type, media_id)
                VALUES ($1, $2, $3)
                ON CONFLICT (tag_id, media_type, media_id) DO NOTHING
                """,
                tag_id,
                media_type,
                media_id,
            )

    rows = await conn.fetch(
        """
        SELECT t.* FROM tags t
        INNER JOIN media_tags mt ON t.id = mt.tag_id
        WHERE mt.media_type = $1 AND mt.media_id = $2
        ORDER BY t.name ASC
        """,
        media_type,
        media_id,
    )
    return [Tag(**dict(row)) for row in rows]


@router.post("/media/{media_type}/{media_id}/add/{tag_id}", response_model=List[Tag])
async def add_tag_to_media(
    media_type: str,
    media_id: int,
    tag_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Add a single tag to a media item
    """
    valid_types = ["movie", "show", "anime", "album", "artist"]
    if media_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid media type. Must be one of: {', '.join(valid_types)}",
        )

    tag_exists = await conn.fetchrow("SELECT id FROM tags WHERE id = $1", tag_id)
    if not tag_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found",
        )

    await conn.execute(
        """
        INSERT INTO media_tags (tag_id, media_type, media_id)
        VALUES ($1, $2, $3)
        ON CONFLICT (tag_id, media_type, media_id) DO NOTHING
        """,
        tag_id,
        media_type,
        media_id,
    )

    rows = await conn.fetch(
        """
        SELECT t.* FROM tags t
        INNER JOIN media_tags mt ON t.id = mt.tag_id
        WHERE mt.media_type = $1 AND mt.media_id = $2
        ORDER BY t.name ASC
        """,
        media_type,
        media_id,
    )
    return [Tag(**dict(row)) for row in rows]


@router.delete("/media/{media_type}/{media_id}/remove/{tag_id}", response_model=List[Tag])
async def remove_tag_from_media(
    media_type: str,
    media_id: int,
    tag_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Remove a single tag from a media item
    """
    valid_types = ["movie", "show", "anime", "album", "artist"]
    if media_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid media type. Must be one of: {', '.join(valid_types)}",
        )

    await conn.execute(
        """
        DELETE FROM media_tags
        WHERE tag_id = $1 AND media_type = $2 AND media_id = $3
        """,
        tag_id,
        media_type,
        media_id,
    )

    rows = await conn.fetch(
        """
        SELECT t.* FROM tags t
        INNER JOIN media_tags mt ON t.id = mt.tag_id
        WHERE mt.media_type = $1 AND mt.media_id = $2
        ORDER BY t.name ASC
        """,
        media_type,
        media_id,
    )
    return [Tag(**dict(row)) for row in rows]


@router.delete("/media/{media_type}/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
async def clear_media_tags(
    media_type: str,
    media_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Remove all tags from a media item
    """
    valid_types = ["movie", "show", "anime", "album", "artist"]
    if media_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid media type. Must be one of: {', '.join(valid_types)}",
        )

    await conn.execute(
        "DELETE FROM media_tags WHERE media_type = $1 AND media_id = $2",
        media_type,
        media_id,
    )
    return None


@router.post("/bulk/{media_type}", response_model=dict)
async def bulk_update_tags(
    media_type: str,
    bulk_data: BulkTagUpdate,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Bulk add/remove tags from multiple media items
    """
    valid_types = ["movie", "show", "anime", "album", "artist"]
    if media_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid media type. Must be one of: {', '.join(valid_types)}",
        )

    if not bulk_data.add_tags and not bulk_data.remove_tags:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must specify at least one tag to add or remove",
        )

    added_count = 0
    removed_count = 0

    async with conn.transaction():
        for tag_id in bulk_data.remove_tags:
            for media_id in bulk_data.media_ids:
                result = await conn.execute(
                    """
                    DELETE FROM media_tags
                    WHERE tag_id = $1 AND media_type = $2 AND media_id = $3
                    """,
                    tag_id,
                    media_type,
                    media_id,
                )
                if result == "DELETE 1":
                    removed_count += 1

        for tag_id in bulk_data.add_tags:
            tag_exists = await conn.fetchrow("SELECT id FROM tags WHERE id = $1", tag_id)
            if not tag_exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Tag with id {tag_id} not found",
                )

            for media_id in bulk_data.media_ids:
                result = await conn.execute(
                    """
                    INSERT INTO media_tags (tag_id, media_type, media_id)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (tag_id, media_type, media_id) DO NOTHING
                    """,
                    tag_id,
                    media_type,
                    media_id,
                )
                if result == "INSERT 0 1":
                    added_count += 1

    return {
        "success": True,
        "added": added_count,
        "removed": removed_count,
        "media_count": len(bulk_data.media_ids),
    }


@router.get("/filter/{media_type}", response_model=List[int])
async def get_media_by_tag(
    media_type: str,
    tag_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Get all media IDs that have a specific tag
    """
    valid_types = ["movie", "show", "anime", "album", "artist"]
    if media_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid media type. Must be one of: {', '.join(valid_types)}",
        )

    rows = await conn.fetch(
        """
        SELECT media_id FROM media_tags
        WHERE media_type = $1 AND tag_id = $2
        """,
        media_type,
        tag_id,
    )
    return [row["media_id"] for row in rows]
