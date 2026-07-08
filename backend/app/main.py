from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.db import init_pool, close_pool
from app.core.http_client import close_http_client
from app.api.v1.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown events."""
    # Initialize database connection pool (connects to PgBouncer)
    await init_pool()
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
