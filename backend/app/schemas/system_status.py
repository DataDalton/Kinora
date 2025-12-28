from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Literal
from datetime import datetime


class ServiceStatus(BaseModel):
    name: str
    status: Literal["healthy", "degraded", "error", "unknown", "not_configured"]
    message: Optional[str] = None
    latencyMs: Optional[float] = None
    details: Optional[Dict[str, Any]] = None


class QueueStatus(BaseModel):
    name: str
    depth: int
    workerCount: int


class CeleryTaskStatus(BaseModel):
    taskName: str
    displayName: str
    schedule: str
    lastRunTime: Optional[datetime] = None
    nextRunTime: Optional[datetime] = None
    lastDurationMs: Optional[int] = None
    lastStatus: Optional[str] = None
    status: Literal["running", "idle", "failed", "unknown"]


class DownloadClientStatus(BaseModel):
    id: int
    name: str
    clientType: str
    status: Literal["connected", "error", "disabled"]
    version: Optional[str] = None
    message: Optional[str] = None


class ExternalApiStatus(BaseModel):
    name: str
    status: Literal["healthy", "error", "not_configured"]
    message: Optional[str] = None
    lastChecked: Optional[datetime] = None


class SystemStatusResponse(BaseModel):
    timestamp: datetime
    version: str
    database: ServiceStatus
    cache: ServiceStatus
    pgBouncer: ServiceStatus
    celery: ServiceStatus
    queues: List[QueueStatus]
    celeryTasks: List[CeleryTaskStatus]
    downloadClients: List[DownloadClientStatus]
    externalApis: Dict[str, ExternalApiStatus]
