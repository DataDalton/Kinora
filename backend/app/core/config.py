from typing import List, Optional
import os
import secrets
from pathlib import Path
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def isRunningInDocker() -> bool:
    """Detect if running inside a Docker container."""
    # Check for .dockerenv file
    if Path("/.dockerenv").exists():
        return True
    # Check cgroup for docker
    try:
        with open("/proc/1/cgroup", "r") as f:
            return "docker" in f.read()
    except:
        pass
    return False


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables
    """

    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "Kinora"
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
    POSTGRES_USER: str = "kinora"
    POSTGRES_PASSWORD: str = "kinora_password"
    POSTGRES_DB: str = "kinora"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str = ""

    # PgBouncer (connection pooler) - auto-configured based on environment detection
    # Docker: pgbouncer:5432 (internal). Local dev: localhost:6432 (exposed port).
    PGBOUNCER_ENABLED: bool = False
    PGBOUNCER_HOST: str = "pgbouncer"
    PGBOUNCER_PORT: int = 5432
    # Admin credentials default to PostgreSQL credentials (set in model_validator)

    # Dragonfly (with defaults)
    DRAGONFLY_HOST: str = "localhost"
    DRAGONFLY_PORT: int = 6379
    DRAGONFLY_PASSWORD: Optional[str] = None
    DRAGONFLY_DB: int = 0
    DRAGONFLY_URL: str = ""

    # Bundled qBittorrent auto-configuration. When enabled (set by the Docker compose)
    # and no download client is configured yet, the backend registers the bundled
    # qBittorrent so setup is not required. A manually configured client always wins.
    # Off by default so host development does not register an unreachable client.
    QBITTORRENT_AUTOCONFIG: bool = False
    QBITTORRENT_HOST: str = "gluetun"
    QBITTORRENT_PORT: int = 8080
    # Credentials the bundled qBittorrent is seeded with (see the bootstrap script).
    QBITTORRENT_USERNAME: str = "admin"
    QBITTORRENT_PASSWORD: str = "adminadmin"
    # Gluetun control server URL. The bundled qBittorrent shares gluetun's network
    # namespace, so the auto-configured client points its VPN safety checks here.
    GLUETUN_URL: str = "http://gluetun:8000"

    # Auto-create the library and download root folders under MEDIA_ROOT/DOWNLOADS_ROOT
    # on first boot, so the setup wizard needs no folder step. Off by default so host
    # development does not create folders on the developer's machine.
    AUTO_ROOT_FOLDERS: bool = False
    MEDIA_ROOT: str = "/kinora/media"
    DOWNLOADS_ROOT: str = "/kinora/torrents"

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

        # Prefer the PostgreSQL password from the secrets volume when present. The
        # bootstrap writes it there (a strong value for fresh installs, the historical
        # default for existing ones), so backend, migrations, and PgBouncer all agree.
        secret_password = self._read_secret_file("postgres_password")
        if secret_password:
            self.POSTGRES_PASSWORD = secret_password

        # Auto-compute DATABASE_URL if not provided. postgresql:// (not postgres://) so
        # SQLAlchemy, used by Alembic migrations, accepts it. asyncpg accepts it too.
        if not self.DATABASE_URL:
            self.DATABASE_URL = (
                f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )

        # Auto-compute DRAGONFLY_URL if not provided
        if not self.DRAGONFLY_URL:
            auth_part = f":{self.DRAGONFLY_PASSWORD}@" if self.DRAGONFLY_PASSWORD else ""
            self.DRAGONFLY_URL = f"redis://{auth_part}{self.DRAGONFLY_HOST}:{self.DRAGONFLY_PORT}/{self.DRAGONFLY_DB}"

        # Auto-compute Celery URLs if not provided
        if not self.CELERY_BROKER_URL:
            self.CELERY_BROKER_URL = self.DRAGONFLY_URL
        if not self.CELERY_RESULT_BACKEND:
            self.CELERY_RESULT_BACKEND = self.DRAGONFLY_URL

        # Auto-configure PgBouncer based on environment
        # In Docker: use internal hostname pgbouncer:5432
        # Local dev: use exposed port localhost:6432
        inDocker = isRunningInDocker()
        if inDocker:
            # Running inside Docker - use internal network
            if self.PGBOUNCER_HOST == "pgbouncer":
                self.PGBOUNCER_ENABLED = True
                self.PGBOUNCER_PORT = 5432
        else:
            # Running locally - use exposed Docker port
            self.PGBOUNCER_ENABLED = True
            self.PGBOUNCER_HOST = "localhost"
            self.PGBOUNCER_PORT = 6432

        return self

    def _read_secret_file(self, name: str) -> Optional[str]:
        """Read a value written by the bootstrap into the secrets dir, or None if absent."""
        secrets_dir = os.getenv("KINORA_SECRETS_DIR", ".")
        path = Path(secrets_dir) / name
        try:
            if path.is_file():
                return path.read_text().strip() or None
        except OSError:
            pass
        return None

    def _get_or_create_secret_key(self, key_name: str) -> str:
        """
        Get or create a persistent secret key stored in a file.

        Uses KINORA_SECRETS_DIR when set (a mounted volume in Docker) so keys
        survive container recreation. Generate-if-absent, never overwritten.
        """
        secrets_dir = os.getenv("KINORA_SECRETS_DIR", ".")
        key_file = Path(secrets_dir) / f".{key_name}"

        # Migrate a legacy key from the working directory if present.
        legacy = Path(f".{key_name}")
        if not key_file.exists() and legacy.exists():
            try:
                key_file.parent.mkdir(parents=True, exist_ok=True)
                key_file.write_text(legacy.read_text().strip())
            except OSError:
                return legacy.read_text().strip()

        if key_file.exists():
            return key_file.read_text().strip()

        new_key = secrets.token_urlsafe(32)
        try:
            key_file.parent.mkdir(parents=True, exist_ok=True)
            key_file.write_text(new_key)
        except OSError:
            pass
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
