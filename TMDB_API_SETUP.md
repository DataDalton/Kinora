# Secrets and Environment Variables Setup

This document covers how API keys and environment variables are handled in Nexarr for different deployment scenarios.

## TMDB API Key Setup

## For Users (Using Official Docker Images)

**Zero configuration required!** Official Docker images from GitHub Container Registry have the TMDB API key embedded during the build process.

### Optional: Override with Your Own Key

You can override the embedded TMDB API key in **three ways** (priority order):

#### 1. Via Frontend Settings Page (Recommended)
1. Log in to Nexarr as an administrator
2. Navigate to **Settings** page
3. Find **"Tmdb Api Key"** under **API Keys** section
4. Click **"Edit"**, paste your API key, and click **"Save"**
5. Get your free API Key from: https://www.themoviedb.org/settings/api (look for "API Key (v3 auth)")

This method stores the key in the database and takes highest priority.

#### 2. Via Environment Variable
Add it to your `.env` file or docker-compose environment:
```bash
TMDB_API_KEY=your_api_key_here
```

#### 3. Embedded Default
Official Docker images have the key pre-configured (lowest priority).

**Priority order:** Database Setting > Environment Variable > Embedded Default

## For Developers (Running from Source)

If you're running Nexarr directly from source code (not using Docker images), you **MUST** provide your own TMDB API key:

1. Get your free API Key from: https://www.themoviedb.org/settings/api
2. Copy the **"API Key (v3 auth)"** value (32-character hex string)
3. Create a `.env` file in the `backend/` directory:
   ```bash
   TMDB_API_KEY=your_api_key_here
   ```

## For Contributors (Building Docker Images)

The TMDB API key is injected during the Docker build process via GitHub Actions:

1. The key is stored as a GitHub Secret: `TMDB_API_KEY`
2. During build, it's passed as a build argument: `--build-arg TMDB_API_KEY=${{ secrets.TMDB_API_KEY }}`
3. The Dockerfile sets it as an environment variable: `ENV TMDB_API_KEY=${TMDB_API_KEY}`
4. The built image contains the embedded key (not visible in source code)

### Local Docker Builds

If you're building Docker images locally for testing:

```bash
docker build \
  --build-arg TMDB_API_KEY=your_api_key_here \
  -f docker/backend.Dockerfile \
  -t nexarr-backend:local \
  ./backend
```

## FAQ

### Why use v3 API Key instead of v4 Read Access Token?

Both provide identical read access to TMDB data. We use the v3 API Key because:
- Shorter (32 characters vs much longer token)
- Our code already uses query parameter authentication
- Same access level as the v4 token for all read operations

### Can I use the Read Access Token instead?

Yes! The v3 API Key and v4 Read Access Token are interchangeable for read operations. Just set `TMDB_API_KEY` to your Read Access Token value and it will work.

### Is this secure?

- **Source code**: No API keys are stored in source code (GitHub Secrets only)
- **Docker images**: The key is embedded in the image environment but not exposed in logs or API responses
- **Runtime**: The key is only used server-side for TMDB API requests
- **Users**: Can override with their own keys if desired

This approach follows the same pattern as Radarr/Sonarr - official builds have an embedded key for zero-config deployment, but users can provide their own if preferred.

---

## GitHub Secrets for CI/CD

If you're forking this repository and want to build your own Docker images, add these secrets to your GitHub repository (Settings → Secrets and variables → Actions → New repository secret):

### Required Secrets

**`TMDB_API_KEY`** (Required)
- Your TMDB API v3 Key from: https://www.themoviedb.org/settings/api
- Look for "API Key (v3 auth)" on that page
- Used by backend Docker builds to embed the key

### Optional Secrets

**`NEXT_PUBLIC_API_URL`** (Optional)
- Default: `http://localhost:8000`
- The backend API URL for the frontend to connect to
- Example for production: `https://api.nexarr.example.com`
- Used by frontend Docker builds

**`NEXT_PUBLIC_WS_URL`** (Optional)
- Default: `ws://localhost:8000`
- The WebSocket URL for real-time updates
- Example for production: `wss://api.nexarr.example.com`
- Used by frontend Docker builds

### Environment Variables Users Can Override

Users deploying Nexarr can override any defaults via `.env` file or docker-compose environment variables:

**Backend overrides:**
- `TMDB_API_KEY` - Use your own TMDB key instead of embedded one
- See [.env.example](.env.example) for all available settings

**Frontend overrides:**
- `NEXT_PUBLIC_API_URL` - Backend API endpoint
- `NEXT_PUBLIC_WS_URL` - WebSocket endpoint for real-time features
