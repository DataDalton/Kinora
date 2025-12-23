from typing import List, Optional
import secrets
from pathlib import Path
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables
    """

    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "Nexarr"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "info"

    # Security (auto-generated if not provided)
    SECRET_KEY: str = ""
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database (with defaults)
    POSTGRES_USER: str = "nexarr"
    POSTGRES_PASSWORD: str = "nexarr_password"
    POSTGRES_DB: str = "nexarr"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str = ""

    # Redis (with defaults)
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0
    REDIS_URL: str = ""

    # Backend
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    BACKEND_WORKERS: int = 4
    BACKEND_RELOAD: bool = True

    # CORS (comma-separated string, parsed in model_validator)
    CORS_ORIGINS: str = ""

    # Celery (with defaults)
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""

    def get_cors_origins(self) -> List[str]:
        """Parse CORS_ORIGINS string into a list"""
        if not self.CORS_ORIGINS:
            return []
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @model_validator(mode="after")
    def setup_defaults(self):
        """
        Auto-generate or compute values that weren't explicitly set
        """
        # Auto-generate security keys if not provided
        if not self.SECRET_KEY:
            self.SECRET_KEY = self._get_or_create_secret_key("secret_key")
        if not self.JWT_SECRET_KEY:
            self.JWT_SECRET_KEY = self._get_or_create_secret_key("jwt_secret_key")

        # Auto-compute DATABASE_URL if not provided
        if not self.DATABASE_URL:
            self.DATABASE_URL = (
                f"postgres://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )

        # Auto-compute REDIS_URL if not provided
        if not self.REDIS_URL:
            auth_part = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
            self.REDIS_URL = f"redis://{auth_part}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

        # Auto-compute Celery URLs if not provided
        if not self.CELERY_BROKER_URL:
            self.CELERY_BROKER_URL = self.REDIS_URL
        if not self.CELERY_RESULT_BACKEND:
            self.CELERY_RESULT_BACKEND = self.REDIS_URL

        return self

    def _get_or_create_secret_key(self, key_name: str) -> str:
        """
        Get or create a persistent secret key stored in a file
        """
        key_file = Path(f".{key_name}")
        if key_file.exists():
            return key_file.read_text().strip()
        else:
            new_key = secrets.token_urlsafe(32)
            key_file.write_text(new_key)
            return new_key

    # External APIs
    # TMDB API v3 Key (injected during Docker build from GitHub Secrets)
    TMDB_API_KEY: str = ""

    # Anilist API is public and free - no authentication needed for read queries

    # OpenSubtitles API Key (optional)
    OPENSUBTITLES_API_KEY: Optional[str] = None

    # Cloudflare Bypass (use localhost for local dev, flaresolverr for Docker)
    FLARESOLVERR_URL: Optional[str] = "http://localhost:8191"
    BYPASSARR_URL: Optional[str] = None
    CLOUDFLARE_BYPASS_METHOD: str = "flaresolverr"

    # Download Clients (configured via database settings during setup)
    # File Paths (configured via database settings during setup)

    # Indexers
    INDEXER_REQUEST_TIMEOUT: int = 30
    INDEXER_MAX_RETRIES: int = 3
    INDEXER_RATE_LIMIT: int = 1

    # RSS Monitoring
    RSS_SYNC_INTERVAL: int = 15

    # Search
    SEARCH_RESULTS_LIMIT: int = 100
    MIN_SEEDERS: int = 5

    # Forward Auth - Default trusted private IP ranges for auto-detection
    FORWARD_AUTH_DEFAULT_TRUSTED_RANGES: List[str] = [
        "127.0.0.1/32",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
    ]


settings = Settings()
