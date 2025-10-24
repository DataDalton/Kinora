FROM python:3.12-slim as base

# Build argument for TMDB API key (injected from GitHub Secrets)
ARG TMDB_API_KEY
ENV TMDB_API_KEY=${TMDB_API_KEY}

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Development stage
FROM base as development

# Copy application code
COPY . .

# Run database migrations and start server with reload
CMD ["sh", "-c", "alembic upgrade head && granian --interface asgi --host 0.0.0.0 --port 8000 --reload app.main:app"]

# Production stage
FROM base as production

# Copy application code
COPY . .

# Run database migrations and start server
CMD ["sh", "-c", "alembic upgrade head && granian --interface asgi --host 0.0.0.0 --port 8000 --workers 4 app.main:app"]
