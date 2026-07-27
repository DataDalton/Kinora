import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
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
                results.append(
                    {
                        "id": client["id"],
                        "name": client["name"],
                        "clientType": client["client_type"],
                        "status": "disabled",
                        "message": "Client disabled",
                    }
                )
            else:
                # Just report as configured - actual connectivity tested elsewhere
                results.append(
                    {
                        "id": client["id"],
                        "name": client["name"],
                        "clientType": client["client_type"],
                        "status": "connected",
                        "message": f"{client['host']}:{client['port']}",
                    }
                )

        return results

    async def checkVpnHealth(self) -> Optional[Dict[str, Any]]:
        """Check gluetun VPN tunnel health. Returns None when gluetun is not configured."""
        try:
            from app.services.gluetun import get_gluetun_client

            gluetun = await get_gluetun_client()
            if not gluetun:
                return None

            vpn_status = await gluetun.get_vpn_status()
            pub = await gluetun.get_public_ip()
            version = await gluetun.get_version()
            up = vpn_status == "running"
            ip = pub.get("public_ip") if pub else None
            country = pub.get("country") if pub else None

            if up and ip:
                status = "connected"
                message = ip + (f" ({country})" if country else "")
            elif up:
                status = "connected"
                message = "Tunnel up"
            else:
                status = "error"
                message = "Tunnel down"

            return {
                "id": -1,
                "name": "VPN (gluetun)",
                "clientType": "gluetun",
                "status": status,
                "version": version,
                "message": message,
            }
        except Exception as e:
            return {
                "id": -1,
                "name": "VPN (gluetun)",
                "clientType": "gluetun",
                "status": "error",
                "version": None,
                "message": str(e),
            }

    async def checkExternalApis(self, conn: asyncpg.Connection) -> Dict[str, Dict[str, Any]]:
        """Check external API connectivity (lightweight checks only)."""
        results = {}

        # Check TMDB - just verify API key is set, don't make network call
        try:
            tmdbKey = await conn.fetchval("SELECT value FROM app_settings WHERE key = $1", "tmdb_api_key")
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
            flareSolverrUrl = await conn.fetchval("SELECT value FROM app_settings WHERE key = $1", "flaresolverr_url")
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

    @staticmethod
    def _scheduleLabel(intervalSeconds: int) -> str:
        if intervalSeconds % 3600 == 0 and intervalSeconds >= 3600:
            hours = intervalSeconds // 3600
            return "Every hour" if hours == 1 else f"Every {hours} hours"
        if intervalSeconds % 60 == 0 and intervalSeconds >= 120:
            return f"Every {intervalSeconds // 60} minutes"
        return f"Every {intervalSeconds} seconds"

    @staticmethod
    def _parseLastRun(timestamp: Optional[str]) -> Optional[datetime]:
        if not timestamp:
            return None
        try:
            return datetime.fromisoformat(timestamp.replace("Z", ""))
        except ValueError:
            return None

    @staticmethod
    def _cronLabel(sched) -> str:
        """Display text for a celery crontab schedule, built from its original spec."""
        minute = str(getattr(sched, "_orig_minute", "*"))
        hour = str(getattr(sched, "_orig_hour", "*"))
        try:
            if hour.startswith("*/"):
                return f"Every {int(hour[2:])} hours"
            if hour != "*" and "," not in hour:
                return f"Daily at {int(hour)}:{int(minute):02d} UTC"
        except ValueError:
            pass
        return f"Cron {minute} {hour} (UTC)"

    @staticmethod
    def _cronNextRun(sched) -> Optional[str]:
        """Next fire time for a celery crontab schedule, ISO UTC."""
        try:
            now = datetime.utcnow()
            remaining = sched.remaining_estimate(now)
            return (now + remaining).isoformat() + "Z"
        except Exception:
            return None

    async def getCeleryTasksStatus(self) -> List[Dict[str, Any]]:
        """
        Status of every scheduled Celery task. Schedules are derived from the two
        places that actually run them, never restated here: dispatcher-driven
        tasks read their interval through the dispatcher's own settings loader,
        and beat-driven tasks read the live beat_schedule entry. Only the display
        name and description are authored in this registry.
        """
        from app.tasks.celery_app import celery_app
        from app.tasks.dispatcher import SCHEDULED_TASKS, _load_intervals

        beat_schedule = celery_app.conf.beat_schedule
        dispatch_minutes = await _load_intervals()

        # taskName matches the task:last_run cache key each task writes. Either
        # "dispatch" (a key in the dispatcher's SCHEDULED_TASKS) or "beat" (a
        # beat_schedule entry name) locates the authoritative schedule.
        tasks = [
            {
                "taskName": "rss_monitor",
                "displayName": "New Upload Monitor",
                "description": "Checks indexer new-upload feeds, auto-downloads matches for monitored media, and grows the local release index.",
                "dispatch": "rss_monitor",
            },
            {
                "taskName": "wanted_search",
                "displayName": "Wanted Movie Search",
                "description": "Searches indexers for monitored movies without a file. Items that keep coming up empty back off automatically.",
                "dispatch": "wanted_search",
            },
            {
                "taskName": "music_wanted_search",
                "displayName": "Wanted Music Search",
                "description": "Searches indexers for wanted albums at the profile's allowed quality tiers, with the same automatic backoff.",
                "dispatch": "music_wanted_search",
            },
            {
                "taskName": "upgrade_search",
                "displayName": "Upgrade Search",
                "description": "Looks for higher-quality versions of downloaded items whose profile allows upgrades.",
                "dispatch": "upgrade_search",
            },
            {
                "taskName": "download_monitor",
                "displayName": "Download Monitor",
                "description": "Tracks download progress in qBittorrent and hands completed downloads to the importer.",
                "beat": "download-monitor-every-minute",
            },
            {
                "taskName": "validation_monitor",
                "displayName": "Validation Monitor",
                "description": "Fallback check for torrents stuck in pre-download validation, for example after a restart.",
                "beat": "validation-monitor",
            },
            {
                "taskName": "seeding_monitor",
                "displayName": "Seeding Rules",
                "description": "Applies seeding rules: ratio and time limits, per-indexer requirements, off-peak throttling, and stall recovery.",
                "beat": "seeding-rules-monitor",
            },
            {
                "taskName": "folder_health",
                "displayName": "Folder Health Check",
                "description": "Verifies every root folder is reachable and writable.",
                "beat": "folder-health-check",
            },
            {
                "taskName": "disk_space_update",
                "displayName": "Disk Space Update",
                "description": "Refreshes the cached free-space numbers shown for root folders.",
                "beat": "folder-disk-space-update",
            },
            {
                "taskName": "metadata_refresh",
                "displayName": "Metadata Refresh",
                "description": "Refreshes metadata for library items with missing data or an unreleased status.",
                "dispatch": "metadata_refresh",
            },
            {
                "taskName": "metadata_prefetch",
                "displayName": "Metadata Prefetch",
                "description": "Warms trending, popular, upcoming, and discover metadata so browse pages answer locally.",
                "dispatch": "metadata_prefetch",
            },
            {
                "taskName": "music_new_releases",
                "displayName": "Music New Releases",
                "description": "Checks monitored artists for newly released albums and adds them as wanted.",
                "dispatch": "music_new_releases",
            },
            {
                "taskName": "yts_sync",
                "displayName": "YTS Catalog Sync",
                "description": "Mirrors the YTS catalog into the local release index, a resumable full crawl first, then small delta pulls.",
                "dispatch": "yts_sync",
            },
        ]

        results = []
        client = await getCacheClient()

        for task in tasks:
            # Resolve the authoritative schedule.
            intervalSeconds = None
            cronSchedule = None
            dailyAtHour = None
            if "dispatch" in task:
                spec = SCHEDULED_TASKS.get(task["dispatch"], {})
                if "daily_at_hour" in spec:
                    dailyAtHour = spec["daily_at_hour"]
                else:
                    minutes = dispatch_minutes.get(task["dispatch"])
                    intervalSeconds = minutes * 60 if minutes else None
            else:
                entry = beat_schedule.get(task["beat"])
                raw = entry.get("schedule") if entry else None
                if isinstance(raw, (int, float)):
                    intervalSeconds = int(raw)
                elif raw is not None:
                    cronSchedule = raw

            if intervalSeconds is not None:
                schedule = self._scheduleLabel(intervalSeconds)
            elif cronSchedule is not None:
                schedule = self._cronLabel(cronSchedule)
            elif dailyAtHour is not None:
                schedule = f"Daily at {dailyAtHour}:00 UTC"
            else:
                schedule = "Not scheduled"

            taskStatus = {
                "taskName": task["taskName"],
                "displayName": task["displayName"],
                "description": task["description"],
                "schedule": schedule,
                "lastRunTime": None,
                "nextRunTime": None,
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
                except Exception:
                    pass

            # Next run: last run plus the interval for interval tasks (the
            # dispatcher or beat fires them on that cadence), the next cron
            # occurrence for cron tasks, the next anchor hour for daily tasks.
            # A missed window fires within a minute of startup, so a computed
            # time in the past reads as "due now".
            if intervalSeconds is not None:
                lastRun = self._parseLastRun(taskStatus["lastRunTime"])
                if lastRun is not None:
                    taskStatus["nextRunTime"] = (lastRun + timedelta(seconds=intervalSeconds)).isoformat() + "Z"
            elif cronSchedule is not None:
                taskStatus["nextRunTime"] = self._cronNextRun(cronSchedule)
            elif dailyAtHour is not None:
                lastRun = self._parseLastRun(taskStatus["lastRunTime"])
                base = lastRun or datetime.utcnow()
                candidate = base.replace(hour=dailyAtHour, minute=0, second=0, microsecond=0)
                if candidate <= base:
                    candidate += timedelta(days=1)
                taskStatus["nextRunTime"] = candidate.isoformat() + "Z"

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
            celeryHealth = {
                "name": "Celery",
                "status": "unknown",
                "message": "Check timed out",
                "details": {"workerCount": 0, "queueDepth": 0},
            }
            celeryTasks = []

        # Run DB-dependent checks sequentially (asyncpg connections aren't concurrent-safe)
        try:
            downloadClients = await self.checkDownloadClients(conn)
        except Exception as e:
            downloadClients = []

        # Append VPN (gluetun) tunnel health when configured.
        try:
            vpnHealth = await self.checkVpnHealth()
            if vpnHealth:
                downloadClients.append(vpnHealth)
        except Exception:
            pass

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
            celeryHealth = {
                "name": "Celery",
                "status": "error",
                "message": str(celeryHealth),
                "details": {"workerCount": 0, "queueDepth": 0},
            }
        if isinstance(celeryTasks, Exception):
            celeryTasks = []

        # Build queues from celery health
        queues = []
        if celeryHealth.get("details"):
            queues.append(
                {
                    "name": "celery",
                    "depth": celeryHealth["details"].get("queueDepth", 0),
                    "workerCount": celeryHealth["details"].get("workerCount", 0),
                }
            )

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
