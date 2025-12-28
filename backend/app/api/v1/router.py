from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, movies, shows, anime, music, search, discover, webtransport, settings, media_profiles, transcoding, library_import, setup, two_factor, tags, history, blocklist, bulk, files, root_folders, permissions, requests

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(two_factor.router, prefix="/2fa", tags=["two-factor-auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(setup.router, prefix="/setup", tags=["setup"])
api_router.include_router(movies.router, prefix="/movies", tags=["movies"])
api_router.include_router(shows.router, prefix="/shows", tags=["shows"])
api_router.include_router(anime.router, prefix="/anime", tags=["anime"])
api_router.include_router(music.router, prefix="/music", tags=["music"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(discover.router, prefix="/discover", tags=["discover"])
api_router.include_router(webtransport.router, prefix="/ws", tags=["real-time"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(media_profiles.router, prefix="/media-profiles", tags=["media-profiles"])
api_router.include_router(transcoding.router, prefix="/transcoding", tags=["transcoding"])
api_router.include_router(library_import.router, prefix="/library-import", tags=["library-import"])
api_router.include_router(tags.router, prefix="/tags", tags=["tags"])
api_router.include_router(history.router, prefix="/history", tags=["history"])
api_router.include_router(blocklist.router, prefix="/blocklist", tags=["blocklist"])
api_router.include_router(bulk.router, prefix="/bulk", tags=["bulk-operations"])
api_router.include_router(files.router, prefix="/files", tags=["file-management"])
api_router.include_router(root_folders.router, prefix="/root-folders", tags=["root-folders"])
api_router.include_router(permissions.router, prefix="/permissions", tags=["permissions"])
api_router.include_router(requests.router, prefix="/requests", tags=["requests"])
