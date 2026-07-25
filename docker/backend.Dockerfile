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
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && rm -rf /var/lib/apt/lists/*

# Add uv to PATH
ENV PATH="/root/.local/bin:$PATH"

# Attempt to install NVIDIA CUDA toolkit for GPU transcoding
# Falls back to software transcoding if unavailable
RUN apt-get update \
    && apt-get install -y nvidia-cuda-toolkit 2>/dev/null \
    || echo "CUDA not available - using software transcoding" \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install Python dependencies with uv
RUN uv sync --frozen --no-dev

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

# Start server with backpressure handling and worker respawning (init runs before server
# starts). http=auto serves HTTP/1.1 and negotiates HTTP/2 when asked. Browser-facing
# HTTP/2 and HTTP/3 over TLS are terminated at the Caddy reverse proxy, which talks HTTP/1.1 here.
CMD ["uv", "run", "python", "scripts/start.py", "--interface", "asgi", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--http", "auto", "--backpressure", "1024", "--respawn-failed-workers", "app.main:app"]
