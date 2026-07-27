from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.db import init_pool, close_pool
from app.core.http_client import close_http_client
from app.api.v1.router import api_router


class ForwardedProtoMiddleware:
    """
    Rewrites the request scheme from the X-Forwarded-Proto header set by the Caddy
    reverse proxy. Caddy terminates TLS and forwards plain HTTP to the backend, so
    without this the backend builds trailing-slash redirects and URLs as http://,
    which browsers block as a cross-origin (https to http) request. This restores the
    original https scheme so redirects stay same-origin and WebSocket URLs use wss.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            headers = dict(scope.get("headers") or [])
            forwarded_proto = headers.get(b"x-forwarded-proto")
            if forwarded_proto:
                proto = forwarded_proto.decode("latin-1").split(",")[0].strip()
                if scope["type"] == "websocket":
                    scope["scheme"] = "wss" if proto == "https" else "ws"
                else:
                    scope["scheme"] = proto
        await self.app(scope, receive, send)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown events."""
    # Initialize database connection pool (connects to PgBouncer)
    await init_pool()
    # Register the bundled qBittorrent and create the root folders on first boot (Docker
    # only, never overriding a manually configured client or existing folders).
    from app.api.v1.endpoints.setup import (
        ensure_bundled_download_client,
        ensure_bundled_root_folders,
        ensure_qbittorrent_interface_binding,
    )

    await ensure_bundled_download_client()
    await ensure_bundled_root_folders()
    await ensure_qbittorrent_interface_binding()
    # Reclaim FlareSolverr browsers held by sessions whose owning process has exited.
    try:
        from app.services.cloudflare.flaresolverr import flaresolverr

        await flaresolverr.reap_orphan_sessions()
    except Exception as e:
        print(f"FlareSolverr session cleanup skipped: {e}")
    yield
    # Shutdown: Close database connection pool and HTTP client
    await close_pool()
    await close_http_client()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Unified media management platform - The fastest, most efficient alternative to Sonarr/Radarr/Prowlarr",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# GZip compression for responses over 1KB
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS configuration
cors_origins = settings.get_cors_origins() or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Trust the proxy's X-Forwarded-Proto. Added last so it wraps the other middleware and
# fixes the scheme before routing builds any redirect or URL.
app.add_middleware(ForwardedProtoMiddleware)

# Include API router
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return JSONResponse(
        content={
            "status": "healthy",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
        }
    )


@app.get("/")
async def root():
    """Root endpoint."""
    return JSONResponse(
        content={
            "message": f"Welcome to {settings.APP_NAME}",
            "version": settings.APP_VERSION,
            "docs": "/api/docs",
        }
    )
