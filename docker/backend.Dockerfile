FROM python:3.14-slim AS base

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    ffmpeg \
    wget \
    util-linux \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Attempt to install NVIDIA CUDA toolkit for GPU transcoding
# Falls back to software transcoding if unavailable
RUN apt-get update \
    && apt-get install -y nvidia-cuda-toolkit 2>/dev/null \
    || echo "CUDA not available - using software transcoding" \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Development stage
FROM base AS development

# Copy application code
COPY . .

# Start server with reload
CMD ["granian", "--interface", "asgi", "--host", "0.0.0.0", "--port", "8000", "--reload", "app.main:app"]

# Production stage
FROM base AS production

# Copy application code
COPY . .

# Start server
CMD ["granian", "--interface", "asgi", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "app.main:app"]
