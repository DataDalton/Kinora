from fastapi import APIRouter, Depends
from typing import List
from app.schemas.movie import MovieSearch
from app.api.v1.endpoints.auth import get_current_user
from app.schemas.user import User

router = APIRouter()


@router.get("/trending", response_model=List[MovieSearch])
async def get_trending(
    media_type: str = "all",
    time_window: str = "week",
    current_user: User = Depends(get_current_user),
):
    """
    Get trending media (placeholder)
    """
    return []


@router.get("/popular", response_model=List[MovieSearch])
async def get_popular(
    media_type: str = "movie",
    current_user: User = Depends(get_current_user),
):
    """
    Get popular media (placeholder)
    """
    return []


@router.get("/upcoming", response_model=List[MovieSearch])
async def get_upcoming(
    media_type: str = "movie",
    current_user: User = Depends(get_current_user),
):
    """
    Get upcoming releases (placeholder)
    """
    return []
