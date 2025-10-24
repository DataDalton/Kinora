# Nexarr - Local Development Setup

Complete guide to get Nexarr running locally for development.

---

## Prerequisites

### Required Software

- **Docker Desktop** (for PostgreSQL, Redis, FlareSolverr)
- **Python 3.12+** (for backend)
- **Node.js 20+** (for frontend)
- **Git**

### Optional

- **qBittorrent** (for download testing)

---

## Quick Start (2 Commands)

### 1. Clone and Navigate

```bash
git clone <your-repo-url>
cd Nexarr
```

### 2. Get Your TMDB API Key

1. Go to <https://www.themoviedb.org/settings/api>
2. Sign up/login
3. Copy your **"API Key (v3 auth)"** (32-character hex string)
4. Add it to `backend/.env` (file will be created automatically on first install):

```bash
TMDB_API_KEY=your_api_key_here
```

### 3. Install Everything

```bash
npm install
```

This single command will:
- Check Docker is running
- Install frontend dependencies
- Create Python virtual environment
- Install backend dependencies
- Create backend/.env template if it doesn't exist

### 4. Run Development Environment

```bash
npm run dev
```

This single command will:
- Start Docker services (PostgreSQL, Redis, FlareSolverr)
- Start backend API server (with auto-reload)
- Start Celery worker (background tasks)
- Start Celery beat (task scheduler)
- Start frontend dev server (with hot-reload)

**Access Points:**
- Frontend: <http://localhost:3000>
- Backend API: <http://localhost:8000>
- API docs: <http://localhost:8000/docs>

---

## First Time Setup

### 1. Register Your First User

1. Open <http://localhost:3000>
2. Click "Sign up" or navigate to <http://localhost:3000/register>
3. Create your admin account

### 2. Initialize Settings (Optional)

1. Navigate to <http://localhost:3000/settings>
2. Click "Initialize Defaults"
3. Configure your TMDB API key if you want to override the default

### 3. Create a Quality Profile

1. Navigate to <http://localhost:3000/quality-profiles>
2. Click "Add Profile"
3. Create a profile (e.g., "1080p Preferred")

### 4. Start Adding Media

- Search: <http://localhost:3000/search>
- Discover: <http://localhost:3000/discover>

---

## Additional Commands

### Stop Development Environment

```bash
npm run docker:down
```

### View Docker Logs

```bash
npm run docker:logs
```

### Reset Database (clean slate)

```bash
npm run docker:reset
```

### Clean Everything (remove all dependencies)

```bash
npm run clean
```

---

## Development Workflow

### Backend Changes

- **Auto-reload enabled**: Save your Python files and Granian will restart automatically
- **View logs**: Check the backend terminal output (cyan)
- **API testing**: Use <http://localhost:8000/docs> (Swagger UI)

### Frontend Changes

- **Hot reload enabled**: Save React/TypeScript files and browser will refresh
- **View logs**: Check the frontend terminal output (green)
- **Dev tools**: Use browser DevTools for debugging

### Database Changes

```bash
# Connect to PostgreSQL
docker exec -it nexarr-postgres psql -U nexarr -d nexarr

# View tables
\dt

# Query example
SELECT * FROM movies LIMIT 10;

# Exit
\q
```

### Redis Monitoring

```bash
# Connect to Redis CLI
docker exec -it nexarr-redis redis-cli

# View keys
KEYS *

# Get cached value
GET "tmdb:search/movie:{'query': 'Inception'}"

# Exit
exit
```

---

## Troubleshooting

### Docker not running

```bash
# The npm install will check if Docker is running
# If it fails, start Docker Desktop and try again
```

### Backend won't start

```bash
# Check if port 8000 is in use
# Windows:
netstat -ano | findstr :8000
# Mac/Linux:
lsof -i :8000

# Check database connection
docker-compose logs postgres

# Manually test database
docker exec -it nexarr-postgres psql -U nexarr -d nexarr -c "SELECT 1;"
```

### Frontend won't start

```bash
# Clear node_modules and reinstall
cd frontend
rm -rf node_modules .next
npm install
cd ..
npm run dev
```

### Celery not working

```bash
# Check Redis is running
docker exec -it nexarr-redis redis-cli ping
# Should return: PONG

# Check Celery tasks
cd backend
venv\Scripts\activate  # or source venv/bin/activate on Mac/Linux
celery -A app.tasks.celery_app inspect active
```

### Database issues

```bash
# Reset database
npm run docker:reset
```

### Port conflicts

Edit [package.json](package.json) scripts to use different ports:
- Backend: Change `--port 8000` to `--port 8001`
- Frontend: Change to `"dev:frontend": "cd frontend && npm run dev -- -p 3001"`

---

## Optional: qBittorrent Setup

For testing actual downloads:

1. **Download qBittorrent**: <https://www.qbittorrent.org/download.php>
2. **Enable Web UI**:
   - Tools → Options → Web UI
   - Check "Enable Web UI"
   - Port: 8080
   - Username: admin
   - Password: adminadmin (or set your own)

3. **Update Backend Config** (if using custom port/credentials):

```bash
# backend/.env
QBITTORRENT_HOST=localhost
QBITTORRENT_PORT=8080
QBITTORRENT_USERNAME=admin
QBITTORRENT_PASSWORD=adminadmin
```

---

## Development Tools

### Recommended VS Code Extensions

- Python
- Pylance
- ESLint
- Prettier
- Tailwind CSS IntelliSense
- Docker

### Database GUI (Optional)

- **pgAdmin**: <https://www.pgadmin.org/>
- Connection details:
  - Host: localhost
  - Port: 5432
  - Database: nexarr
  - Username: nexarr
  - Password: nexarr_password

### Redis GUI (Optional)

- **Redis Insight**: <https://redis.com/redis-enterprise/redis-insight/>
- Connection: redis://localhost:6379

---

## Environment Variables Reference

### Backend (.env)

```bash
# Required
TMDB_API_KEY=your_api_key_here

# Optional overrides
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=nexarr
POSTGRES_PASSWORD=nexarr_password
POSTGRES_DB=nexarr

REDIS_HOST=localhost
REDIS_PORT=6379

QBITTORRENT_HOST=localhost
QBITTORRENT_PORT=8080
QBITTORRENT_USERNAME=admin
QBITTORRENT_PASSWORD=adminadmin

# OpenSubtitles (optional)
OPENSUBTITLES_API_KEY=your_key_here
```

### Frontend (.env.local) - Optional

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Production Build Testing

To test production builds locally:

```bash
# Build and run with Docker Compose
docker-compose up --build

# Access at http://localhost:3000
```

---

## Next Steps

1. ✓ Dev environment running
2. ✓ Create your first user
3. ✓ Add some movies/shows
4. ✓ Test torrent searching
5. ✓ Monitor downloads in activity page
6. Start building new features!

---

## Getting Help

- **Check logs** in the terminal output (color-coded by service)
- **API errors**: <http://localhost:8000/docs>
- **Database issues**: `docker-compose logs postgres`
- **Frontend errors**: Browser DevTools Console
