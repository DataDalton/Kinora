# Nexarr Quick Start Guide

Get Nexarr running in under 5 minutes!

## Prerequisites

- **Docker** and **Docker Compose** installed
- **TMDB API Key** (free at https://www.themoviedb.org/settings/api)

That's it! Everything else is automatic.

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/nexarr.git
cd nexarr
```

### 2. Configure TMDB API Key (Required)

Create a `.env` file:

```bash
echo "TMDB_API_KEY=your_api_key_here" > .env
```

**That's the only required configuration!** All other settings have sensible defaults.

### 3. Start Nexarr

```bash
docker-compose up -d
```

First startup will:
- Build Docker images (~2-3 minutes)
- Initialize PostgreSQL database
- Create database tables automatically
- Auto-generate security keys
- Start all services

### 4. Access Nexarr

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/api/docs

## First Use

### Register Your Account

```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "email": "admin@example.com",
    "password": "YourSecurePassword123"
  }'
```

### Login

```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=YourSecurePassword123"
```

Save the `access_token` from the response.

### Search for a Movie

```bash
curl "http://localhost:8000/api/v1/search?query=Iron%20Man" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Add Movie to Library

```bash
curl -X POST "http://localhost:8000/api/v1/movies" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Iron Man",
    "tmdb_id": 1726,
    "monitored": true
  }'
```

## Services

Nexarr consists of:

- **PostgreSQL** (port 5432): Database
- **Dragonfly** (port 6379): Caching and task queue
- **Backend** (port 8000): FastAPI application
- **Frontend** (port 3000): Next.js application
- **Celery Worker**: Background tasks
- **Celery Beat**: Scheduled tasks
- **FlareSolverr** (port 8191): Cloudflare bypass

## Optional Configuration

### Connect qBittorrent

If you have qBittorrent running, add to `.env`:

```env
QBITTORRENT_HOST=192.168.1.100
QBITTORRENT_PORT=8080
QBITTORRENT_USERNAME=admin
QBITTORRENT_PASSWORD=adminadmin
```

### Custom Download Paths

```env
MEDIA_ROOT=/path/to/media
DOWNLOADS_ROOT=/path/to/downloads
```

### Enable Anilist (for Anime)

Get OAuth credentials at https://anilist.co/settings/developer

```env
ANILIST_CLIENT_ID=your_client_id
ANILIST_CLIENT_SECRET=your_client_secret
```

## Development Mode

For development with hot reload:

```bash
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
```

Changes to code will automatically reload both backend and frontend.

## Troubleshooting

### Backend won't start

Check logs:
```bash
docker-compose logs backend
```

Common issues:
- TMDB_API_KEY not set → Add to `.env`
- Port 8000 in use → Change `BACKEND_PORT` in `.env`

### Database connection failed

```bash
docker-compose restart postgres
docker-compose logs postgres
```

### Frontend can't connect to backend

Check CORS settings in `.env`:
```env
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
```

### Clear everything and start fresh

```bash
docker-compose down -v
docker-compose up -d
```

## What's Next?

1. **Explore API Docs**: http://localhost:8000/api/docs
2. **Configure Quality Profiles**: Define your preferred quality settings
3. **Add Media**: Start building your library
4. **Set Up Automation**: Configure RSS monitoring and wanted searches

## Performance Tips

- **PostgreSQL**: Has 50-connection pool by default (handles heavy load)
- **Dragonfly**: Used for caching (1-hour cache on metadata)
- **Indexers**: Rate-limited to 1 request/second (configurable)
- **Celery**: RSS monitoring every 15 minutes (configurable)

## Useful Commands

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f celery-worker
```

### Restart Service
```bash
docker-compose restart backend
```

### Update Nexarr
```bash
git pull
docker-compose down
docker-compose up -d --build
```

### Backup Database
```bash
docker exec nexarr-postgres pg_dump -U nexarr nexarr > backup.sql
```

### Restore Database
```bash
cat backup.sql | docker exec -i nexarr-postgres psql -U nexarr nexarr
```

## Support

- **Issues**: https://github.com/yourusername/nexarr/issues
- **Discussions**: https://github.com/yourusername/nexarr/discussions

---

**Enjoy Nexarr!**
