from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, movies, shows, anime, search, discover, webtransport, settings, media_profiles, transcoding, library_import, setup

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(setup.router, prefix="/setup", tags=["setup"])
api_router.include_router(movies.router, prefix="/movies", tags=["movies"])
api_router.include_router(shows.router, prefix="/shows", tags=["shows"])
api_router.include_router(anime.router, prefix="/anime", tags=["anime"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(discover.router, prefix="/discover", tags=["discover"])
api_router.include_router(webtransport.router, prefix="/ws", tags=["real-time"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(media_profiles.router, prefix="/media-profiles", tags=["media-profiles"])
api_router.include_router(transcoding.router, prefix="/transcoding", tags=["transcoding"])
api_router.include_router(library_import.router, prefix="/library-import", tags=["library-import"])
