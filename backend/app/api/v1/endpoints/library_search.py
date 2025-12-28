from fastapi import APIRouter, Depends, Query
from typing import List, Dict, Any
import asyncpg

from app.db import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.schemas.user import UserWithPermissions

router = APIRouter()


@router.get("/")
async def searchLibrary(
    query: str = Query(..., min_length=1),
    limit: int = Query(5, ge=1, le=20),
    currentUser: UserWithPermissions = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Search across all media types in the library."""
    searchPattern = f"%{query}%"

    results = await conn.fetch("""
        WITH combined AS (
            SELECT id, title, poster_path, 'movie' as media_type FROM movies WHERE title ILIKE $1
            UNION ALL
            SELECT id, title, poster_path, 'show' as media_type FROM shows WHERE title ILIKE $1
            UNION ALL
            SELECT id, title, poster_path, 'anime' as media_type FROM anime WHERE title ILIKE $1
            UNION ALL
            SELECT id, name as title, picture_medium as poster_path, 'artist' as media_type FROM artists WHERE name ILIKE $1
            UNION ALL
            SELECT id, title, cover_medium as poster_path, 'album' as media_type FROM albums WHERE title ILIKE $1
        )
        SELECT * FROM combined LIMIT $2
    """, searchPattern, limit)

    return [dict(row) for row in results]
