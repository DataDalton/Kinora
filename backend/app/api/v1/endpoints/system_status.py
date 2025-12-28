from fastapi import APIRouter, Depends
import asyncpg
from typing import List

from app.db import get_db
from app.api.v1.endpoints.auth import get_current_user, require_permission
from app.schemas.user import UserWithPermissions
from app.schemas.system_status import SystemStatusResponse, CeleryTaskStatus
from app.services.system_health import systemHealthMonitor
from app.core.cache import cacheDelete

router = APIRouter()


@router.get("/", response_model=SystemStatusResponse)
async def getSystemStatus(
    conn: asyncpg.Connection = Depends(get_db),
    currentUser: UserWithPermissions = Depends(get_current_user),
):
    """Get comprehensive system health status."""
    return await systemHealthMonitor.getFullSystemStatus(conn)


@router.get("/celery/tasks", response_model=List[CeleryTaskStatus])
async def getCeleryTasksStatus(
    currentUser: UserWithPermissions = Depends(get_current_user),
):
    """Get detailed Celery task execution status."""
    return await systemHealthMonitor.getCeleryTasksStatus()


@router.post("/refresh")
async def refreshSystemStatus(
    conn: asyncpg.Connection = Depends(get_db),
    currentUser: UserWithPermissions = Depends(require_permission("system.admin")),
):
    """Force refresh all health checks (bypasses cache)."""
    await cacheDelete("health:system_status")
    return await systemHealthMonitor.getFullSystemStatus(conn)
