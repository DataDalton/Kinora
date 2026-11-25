FROM python:3.14-slim AS base

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system dependencies and uv
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    ffmpeg \
    wget \
    util-linux \
    gnupg \
    curl \
    && curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh \
    && rm -rf /var/lib/apt/lists/*

# The app runs as an unprivileged user. uv lives in /usr/local/bin so any user can run
# it, the environment is never re-synced at runtime (UV_NO_SYNC) because the runtime
# user does not own it, and caches go to /tmp. Compose picks the user id with PUID and
# PGID, and the kinora user covers the default of 1000.
ENV UV_NO_SYNC=1 \
    UV_CACHE_DIR=/tmp/uv-cache \
    HOME=/home/kinora
RUN groupadd --gid 1000 kinora \
    && useradd --uid 1000 --gid 1000 --home-dir /home/kinora --create-home --shell /usr/sbin/nologin kinora \
    && chmod 0777 /home/kinora

# Attempt to install NVIDIA CUDA toolkit for GPU transcoding
# Falls back to software transcoding if unavailable
RUN apt-get update \
    && apt-get install -y nvidia-cuda-toolkit 2>/dev/null \
    || echo "CUDA not available - using software transcoding" \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install Python dependencies with uv
RUN uv sync --frozen --no-dev --no-cache

# Development stage
FROM base AS development

# Copy application code
COPY . .

# Start server with reload (init runs before server starts). http=auto serves HTTP/1.1
# for direct browser/curl access and negotiates HTTP/2 when asked. HTTP/2 and HTTP/3 for
# browsers are terminated at the Caddy reverse proxy over TLS, which talks HTTP/1.1 here.
CMD ["uv", "run", "python", "scripts/start.py", "--interface", "asgi", "--host", "0.0.0.0", "--port", "8000", "--reload", "--http", "auto", "app.main:app"]

# Production stage
FROM base AS production

# Copy application code
COPY . .

USER kinora

# Start server with backpressure handling and worker respawning (init runs before server
# starts). http=auto serves HTTP/1.1 and negotiates HTTP/2 when asked. Browser-facing
# HTTP/2 and HTTP/3 over TLS are terminated at the Caddy reverse proxy, which talks HTTP/1.1 here.
CMD ["uv", "run", "python", "scripts/start.py", "--interface", "asgi", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--http", "auto", "--backpressure", "1024", "--respawn-failed-workers", "app.main:app"]
