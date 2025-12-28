"""
Celery tasks for folder health monitoring and disk space updates.
"""
import asyncpg
import time
from datetime import datetime

from app.tasks.celery_app import celery_app, runAsync
from app.core.config import settings
from app.services.folder_health import folderHealthMonitor
from app.services.folder_selector import folderSelector
from app.core.cache import cacheSet


@celery_app.task(name="app.tasks.folder_health.check_folder_health")
def checkFolderHealth():
    """
    Periodic task to check health status of all active root folders.
    Runs every 5 minutes to detect accessibility issues.
    """
    async def asyncCheckHealth():
        taskName = "folder_health"
        startTime = time.time()
        status = "success"

        conn = await asyncpg.connect(settings.DATABASE_URL)
        try:
            results = await folderHealthMonitor.checkAllFolders(conn)
            healthyCnt = sum(1 for f in results if f.get("health_status") == "healthy")
            warningCnt = sum(1 for f in results if f.get("health_status") == "warning")
            errorCnt = sum(1 for f in results if f.get("health_status") == "error")

            return {
                "checked": len(results),
                "healthy": healthyCnt,
                "warning": warningCnt,
                "error": errorCnt
            }
        except Exception as e:
            status = "failed"
            raise
        finally:
            await conn.close()
            elapsedMs = int((time.time() - startTime) * 1000)
            await cacheSet(f"task:last_run:{taskName}", {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "status": status,
                "durationMs": elapsedMs,
            }, expire=86400)

    return runAsync(asyncCheckHealth())


@celery_app.task(name="app.tasks.folder_health.update_disk_space")
def updateDiskSpace():
    """
    Periodic task to update cached disk space values for all root folders.
    Runs every minute to keep space information current.
    """
    async def asyncUpdateSpace():
        taskName = "disk_space_update"
        startTime = time.time()
        status = "success"

        conn = await asyncpg.connect(settings.DATABASE_URL)
        try:
            # Get all active folders
            rows = await conn.fetch(
                "SELECT id FROM root_folders WHERE is_active = true"
            )

            updatedCnt = 0
            for row in rows:
                await folderSelector.updateDiskSpaceCache(conn, row["id"])
                updatedCnt += 1

            return {"updated": updatedCnt}
        except Exception as e:
            status = "failed"
            raise
        finally:
            await conn.close()
            elapsedMs = int((time.time() - startTime) * 1000)
            await cacheSet(f"task:last_run:{taskName}", {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "status": status,
                "durationMs": elapsedMs,
            }, expire=86400)

    return runAsync(asyncUpdateSpace())


@celery_app.task(name="app.tasks.folder_health.check_single_folder")
def checkSingleFolder(folderId: int):
    """
    On-demand task to check health of a specific folder.
    Can be triggered manually from the API.
    """
    async def asyncCheckFolder():
        conn = await asyncpg.connect(settings.DATABASE_URL)
        try:
            folder = await folderSelector.getFolder(conn, folderId)
            if not folder:
                return {"error": "Folder not found"}

            # Update disk space
            await folderSelector.updateFolderDiskSpace(folder)

            # Check health
            status, message = await folderHealthMonitor.checkFolderHealth(folder)

            # Update in database
            await folderHealthMonitor.updateFolderHealth(conn, folderId, status, message)

            return {
                "folder_id": folderId,
                "status": status,
                "message": message
            }
        finally:
            await conn.close()

    return runAsync(asyncCheckFolder())
