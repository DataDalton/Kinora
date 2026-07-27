export type ServiceStatusLevel =
	| "healthy"
	| "degraded"
	| "error"
	| "unknown"
	| "not_configured";
export type TaskStatusLevel = "running" | "idle" | "failed" | "unknown";
export type DownloadClientStatusLevel = "connected" | "error" | "disabled";
export type ApiStatusLevel = "healthy" | "error" | "not_configured";

export interface ServiceStatus {
	name: string;
	status: ServiceStatusLevel;
	message: string | null;
	latencyMs: number | null;
	details?: Record<string, unknown>;
}

export interface QueueStatus {
	name: string;
	depth: number;
	workerCount: number;
}

export interface CeleryTaskStatus {
	taskName: string;
	displayName: string;
	description: string;
	schedule: string;
	lastRunTime: string | null;
	nextRunTime: string | null;
	lastDurationMs: number | null;
	lastStatus: string | null;
	status: TaskStatusLevel;
}

export interface DownloadClientStatus {
	id: number;
	name: string;
	clientType: string;
	status: DownloadClientStatusLevel;
	version: string | null;
	message: string | null;
}

export interface ExternalApiStatus {
	name: string;
	status: ApiStatusLevel;
	message: string | null;
	lastChecked: string | null;
}

export interface SystemStatusResponse {
	timestamp: string;
	version: string;
	database: ServiceStatus;
	cache: ServiceStatus;
	pgBouncer: ServiceStatus;
	celery: ServiceStatus;
	queues: QueueStatus[];
	celeryTasks: CeleryTaskStatus[];
	downloadClients: DownloadClientStatus[];
	externalApis: Record<string, ExternalApiStatus>;
}
