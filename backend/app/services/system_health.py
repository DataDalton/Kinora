import asyncio
import time
from datetime import datetime
from typing import Dict, Any, List
import asyncpg

from app.core.cache import cacheGet, cacheSet, getCacheClient
from app.db import get_pool
from app.core.config import settings


HEALTH_CACHE_TTL = 30  # 30 seconds


class SystemHealthMonitor:

    async def checkDatabaseHealth(self) -> Dict[str, Any]:
        """Check database connection and latency."""
        try:
            pool = await get_pool()
            startTime = time.time()
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            latencyMs = (time.time() - startTime) * 1000

            return {
                "name": "PostgreSQL",
                "status": "healthy",
                "latencyMs": round(latencyMs, 2),
                "message": None,
            }
        except Exception as e:
            return {
                "name": "PostgreSQL",
                "status": "error",
                "latencyMs": None,
                "message": str(e),
            }

    async def checkCacheHealth(self) -> Dict[str, Any]:
        """Check Dragonfly/Redis connection."""
        try:
            client = await getCacheClient()
            if client is None:
                return {
                    "name": "Dragonfly",
                    "status": "error",
                    "message": "Cache client not available",
                }

            startTime = time.time()
            await client.ping()
            latencyMs = (time.time() - startTime) * 1000

            # Get memory info
            info = await client.info("memory")
            usedMemory = info.get("used_memory", 0)

            return {
                "name": "Dragonfly",
                "status": "healthy",
                "latencyMs": round(latencyMs, 2),
                "message": None,
                "details": {
                    "usedMemoryBytes": usedMemory,
                },
            }
        except Exception as e:
            return {
                "name": "Dragonfly",
                "status": "error",
                "latencyMs": None,
                "message": str(e),
            }

    async def checkPgBouncerHealth(self) -> Dict[str, Any]:
        """Check PgBouncer connection pooler status via database connectivity test."""
        if not settings.PGBOUNCER_ENABLED:
            return {
                "name": "PgBouncer",
                "status": "not_configured",
                "message": "PgBouncer not enabled",
                "latencyMs": None,
            }

        try:
            startTime = time.time()

            # Connect through PgBouncer to the actual database (not admin console)
            # This verifies PgBouncer is accepting and proxying connections
            conn = await asyncpg.connect(
                host=settings.PGBOUNCER_HOST,
                port=settings.PGBOUNCER_PORT,
                user=settings.POSTGRES_USER,
                password=settings.POSTGRES_PASSWORD,
                database=settings.POSTGRES_DB,
                timeout=2.0,
            )

            try:
                # Simple query to verify the connection works through PgBouncer
                await conn.fetchval("SELECT 1")
                latencyMs = (time.time() - startTime) * 1000

                return {
                    "name": "PgBouncer",
                    "status": "healthy",
                    "latencyMs": round(latencyMs, 2),
                    "message": None,
                }
            finally:
                await conn.close()

        except Exception as e:
            return {
                "name": "PgBouncer",
                "status": "error",
                "latencyMs": None,
                "message": str(e),
            }

    async def checkCeleryHealth(self) -> Dict[str, Any]:
        """Check Celery worker status via Redis queue inspection (fast, async-safe)."""
        try:
            # Use Redis/Dragonfly directly to check queue - much faster than Celery inspector
            client = await getCacheClient()
            queueDepth = 0
            workerCount = 0

            if client:
                try:
                    queueDepth = await client.llen("celery")
                    # Check for worker heartbeat keys to estimate worker count
                    workerKeys = await client.keys("celery-task-meta-*")
                    workerCount = 1 if workerKeys else 0  # Assume at least 1 worker if tasks exist
                except:
                    pass

            # If we have a queue but no workers, that's degraded
            if queueDepth > 0 and workerCount == 0:
                status = "degraded"
                message = "Queue has pending tasks but no workers detected"
            elif workerCount > 0:
                status = "healthy"
                message = None
            else:
                status = "healthy"  # Assume healthy if no queue backlog
                message = None

            return {
                "name": "Celery",
                "status": status,
                "message": message,
                "latencyMs": None,
                "details": {
                    "workerCount": workerCount,
                    "activeTaskCount": 0,
                    "queueDepth": queueDepth,
                },
            }
        except Exception as e:
            return {
                "name": "Celery",
                "status": "error",
                "message": str(e),
                "latencyMs": None,
                "details": {
                    "workerCount": 0,
                    "activeTaskCount": 0,
                    "queueDepth": 0,
                },
            }

    async def checkDownloadClients(self, conn: asyncpg.Connection) -> List[Dict[str, Any]]:
        """Check download client status (lightweight - no network calls)."""
        results = []

        clients = await conn.fetch("""
            SELECT id, name, client_type, host, port, is_enabled
            FROM download_clients
        """)

        for client in clients:
            if not client["is_enabled"]:
                results.append({
                    "id": client["id"],
                    "name": client["name"],
                    "clientType": client["client_type"],
                    "status": "disabled",
                    "message": "Client disabled",
                })
            else:
                # Just report as configured - actual connectivity tested elsewhere
                results.append({
                    "id": client["id"],
                    "name": client["name"],
                    "clientType": client["client_type"],
                    "status": "connected",
                    "message": f"{client['host']}:{client['port']}",
                })

        return results

    async def checkExternalApis(self, conn: asyncpg.Connection) -> Dict[str, Dict[str, Any]]:
        """Check external API connectivity (lightweight checks only)."""
        results = {}

        # Check TMDB - just verify API key is set, don't make network call
        try:
            tmdbKey = await conn.fetchval(
                "SELECT value FROM app_settings WHERE key = $1",
                "tmdb_api_key"
            )
            if tmdbKey or settings.TMDB_API_KEY:
                results["tmdb"] = {
                    "name": "TMDB",
                    "status": "healthy",
                    "message": "API key configured",
                    "lastChecked": datetime.utcnow().isoformat() + "Z",
                }
            else:
                results["tmdb"] = {
                    "name": "TMDB",
                    "status": "not_configured",
                    "message": "API key not set",
                }
        except Exception as e:
            results["tmdb"] = {
                "name": "TMDB",
                "status": "error",
                "message": str(e),
            }

        # Check Anilist (public API, always available)
        results["anilist"] = {
            "name": "Anilist",
            "status": "healthy",
            "message": "Public API",
            "lastChecked": datetime.utcnow().isoformat() + "Z",
        }

        # Check FlareSolverr - just verify URL is set, don't make network call
        try:
            flareSolverrUrl = await conn.fetchval(
                "SELECT value FROM app_settings WHERE key = $1",
                "flaresolverr_url"
            )
            if flareSolverrUrl or settings.FLARESOLVERR_URL:
                results["flaresolverr"] = {
                    "name": "FlareSolverr",
                    "status": "healthy",
                    "message": "URL configured",
                    "lastChecked": datetime.utcnow().isoformat() + "Z",
                }
            else:
                results["flaresolverr"] = {
                    "name": "FlareSolverr",
                    "status": "not_configured",
                    "message": "URL not set",
                }
        except Exception as e:
            results["flaresolverr"] = {
                "name": "FlareSolverr",
                "status": "error",
                "message": str(e),
            }

        return results

    async def getCeleryTasksStatus(self) -> List[Dict[str, Any]]:
        """Get status of scheduled Celery tasks."""
        tasks = [
            {"taskName": "rss_monitor", "displayName": "RSS Monitor", "schedule": "Every 5 minutes"},
            {"taskName": "wanted_search", "displayName": "Wanted Media Search", "schedule": "Every 15 minutes"},
            {"taskName": "download_monitor", "displayName": "Download Monitor", "schedule": "Every 60 seconds"},
            {"taskName": "metadata_refresh", "displayName": "Metadata Refresh", "schedule": "Daily at 3 AM"},
            {"taskName": "music_wanted_search", "displayName": "Music Wanted Search", "schedule": "Every 15 minutes"},
            {"taskName": "music_new_releases", "displayName": "Music New Releases", "schedule": "Every 6 hours"},
            {"taskName": "validation_monitor", "displayName": "Validation Monitor", "schedule": "Every 5 minutes"},
            {"taskName": "folder_health", "displayName": "Folder Health Check", "schedule": "Every 5 minutes"},
            {"taskName": "disk_space_update", "displayName": "Disk Space Update", "schedule": "Every 60 seconds"},
        ]

        results = []
        client = await getCacheClient()

        for task in tasks:
            taskStatus = {
                **task,
                "lastRunTime": None,
                "lastDurationMs": None,
                "lastStatus": None,
                "status": "unknown",
            }

            if client:
                try:
                    cached = await client.get(f"task:last_run:{task['taskName']}")
                    if cached:
                        import json
                        data = json.loads(cached)
                        taskStatus["lastRunTime"] = data.get("timestamp")
                        taskStatus["lastDurationMs"] = data.get("durationMs")
                        taskStatus["lastStatus"] = data.get("status")
                        taskStatus["status"] = "idle" if data.get("status") == "success" else "failed"
                except:
                    pass

            results.append(taskStatus)

        return results

    async def getFullSystemStatus(self, conn: asyncpg.Connection) -> Dict[str, Any]:
        """Get complete system status with caching."""
        # Check cache first
        cached = await cacheGet("health:system_status")
        if cached:
            return cached

        # Run non-DB checks in parallel
        try:
            results = await asyncio.wait_for(
                asyncio.gather(
                    self.checkDatabaseHealth(),
                    self.checkCacheHealth(),
                    self.checkPgBouncerHealth(),
                    self.checkCeleryHealth(),
                    self.getCeleryTasksStatus(),
                    return_exceptions=True,
                ),
                timeout=3.0,
            )
            dbHealth, cacheHealth, pgBouncerHealth, celeryHealth, celeryTasks = results
        except asyncio.TimeoutError:
            dbHealth = {"name": "PostgreSQL", "status": "unknown", "message": "Check timed out"}
            cacheHealth = {"name": "Dragonfly", "status": "unknown", "message": "Check timed out"}
            pgBouncerHealth = {"name": "PgBouncer", "status": "unknown", "message": "Check timed out"}
            celeryHealth = {"name": "Celery", "status": "unknown", "message": "Check timed out", "details": {"workerCount": 0, "queueDepth": 0}}
            celeryTasks = []

        # Run DB-dependent checks sequentially (asyncpg connections aren't concurrent-safe)
        try:
            downloadClients = await self.checkDownloadClients(conn)
        except Exception as e:
            downloadClients = []

        try:
            externalApis = await self.checkExternalApis(conn)
        except Exception as e:
            externalApis = {}

        # Handle exceptions from gather
        if isinstance(dbHealth, Exception):
            dbHealth = {"name": "PostgreSQL", "status": "error", "message": str(dbHealth)}
        if isinstance(cacheHealth, Exception):
            cacheHealth = {"name": "Dragonfly", "status": "error", "message": str(cacheHealth)}
        if isinstance(pgBouncerHealth, Exception):
            pgBouncerHealth = {"name": "PgBouncer", "status": "error", "message": str(pgBouncerHealth)}
        if isinstance(celeryHealth, Exception):
            celeryHealth = {"name": "Celery", "status": "error", "message": str(celeryHealth), "details": {"workerCount": 0, "queueDepth": 0}}
        if isinstance(celeryTasks, Exception):
            celeryTasks = []

        # Build queues from celery health
        queues = []
        if celeryHealth.get("details"):
            queues.append({
                "name": "celery",
                "depth": celeryHealth["details"].get("queueDepth", 0),
                "workerCount": celeryHealth["details"].get("workerCount", 0),
            })

        result = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "version": settings.APP_VERSION,
            "database": dbHealth,
            "cache": cacheHealth,
            "pgBouncer": pgBouncerHealth,
            "celery": celeryHealth,
            "queues": queues,
            "celeryTasks": celeryTasks,
            "downloadClients": downloadClients,
            "externalApis": externalApis,
        }

        # Cache for 15 seconds
        await cacheSet("health:system_status", result, expire=15)

        return result


systemHealthMonitor = SystemHealthMonitor()
