import api from "../api";
import type {
	SystemStatusResponse,
	CeleryTaskStatus,
	ServiceStatus,
	QueueStatus,
	DownloadClientStatus,
	ExternalApiStatus,
} from "../../types/system-status";

// Cast to correct types
function transformServiceStatus(data: Record<string, unknown>): ServiceStatus {
	return {
		name: data.name as string,
		status: data.status as ServiceStatus["status"],
		message: (data.message as string | null) ?? null,
		latencyMs: (data.latencyMs as number | null) ?? null,
		details: data.details as Record<string, unknown> | undefined,
	};
}

function transformQueueStatus(data: Record<string, unknown>): QueueStatus {
	return {
		name: data.name as string,
		depth: data.depth as number,
		workerCount: data.workerCount as number,
	};
}

function transformCeleryTaskStatus(
	data: Record<string, unknown>,
): CeleryTaskStatus {
	return {
		taskName: data.taskName as string,
		displayName: data.displayName as string,
		description: (data.description as string) ?? "",
		schedule: data.schedule as string,
		lastRunTime: (data.lastRunTime as string | null) ?? null,
		nextRunTime: (data.nextRunTime as string | null) ?? null,
		lastDurationMs: (data.lastDurationMs as number | null) ?? null,
		lastStatus: (data.lastStatus as string | null) ?? null,
		status: data.status as CeleryTaskStatus["status"],
	};
}

function transformDownloadClientStatus(
	data: Record<string, unknown>,
): DownloadClientStatus {
	return {
		id: data.id as number,
		name: data.name as string,
		clientType: data.clientType as string,
		status: data.status as DownloadClientStatus["status"],
		version: (data.version as string | null) ?? null,
		message: (data.message as string | null) ?? null,
	};
}

function transformExternalApiStatus(
	data: Record<string, unknown>,
): ExternalApiStatus {
	return {
		name: data.name as string,
		status: data.status as ExternalApiStatus["status"],
		message: (data.message as string | null) ?? null,
		lastChecked: (data.lastChecked as string | null) ?? null,
	};
}

// Default service status for missing data
const defaultServiceStatus: ServiceStatus = {
	name: "Unknown",
	status: "unknown",
	message: null,
	latencyMs: null,
};

// Transform the full system status response
function transformSystemStatusResponse(
	data: Record<string, unknown>,
): SystemStatusResponse {
	const externalApisRaw = data.externalApis as
		| Record<string, Record<string, unknown>>
		| undefined;
	const externalApis: Record<string, ExternalApiStatus> = {};

	if (externalApisRaw) {
		for (const [key, value] of Object.entries(externalApisRaw)) {
			externalApis[key] = transformExternalApiStatus(value);
		}
	}

	const queuesRaw = data.queues as Record<string, unknown>[] | undefined;
	const celeryTasksRaw = data.celeryTasks as
		| Record<string, unknown>[]
		| undefined;
	const downloadClientsRaw = data.downloadClients as
		| Record<string, unknown>[]
		| undefined;
	const databaseRaw = data.database as Record<string, unknown> | undefined;
	const cacheRaw = data.cache as Record<string, unknown> | undefined;
	const pgBouncerRaw = data.pgBouncer as Record<string, unknown> | undefined;
	const celeryRaw = data.celery as Record<string, unknown> | undefined;

	return {
		timestamp: (data.timestamp as string) || new Date().toISOString(),
		version: (data.version as string) || "unknown",
		database: databaseRaw
			? transformServiceStatus(databaseRaw)
			: defaultServiceStatus,
		cache: cacheRaw
			? transformServiceStatus(cacheRaw)
			: defaultServiceStatus,
		pgBouncer: pgBouncerRaw
			? transformServiceStatus(pgBouncerRaw)
			: defaultServiceStatus,
		celery: celeryRaw
			? transformServiceStatus(celeryRaw)
			: defaultServiceStatus,
		queues: queuesRaw ? queuesRaw.map(transformQueueStatus) : [],
		celeryTasks: celeryTasksRaw
			? celeryTasksRaw.map(transformCeleryTaskStatus)
			: [],
		downloadClients: downloadClientsRaw
			? downloadClientsRaw.map(transformDownloadClientStatus)
			: [],
		externalApis,
	};
}

export async function getSystemStatus(): Promise<SystemStatusResponse> {
	const response = await api.get("/system/status");
	return transformSystemStatusResponse(response.data);
}

export async function getCeleryTasks(): Promise<CeleryTaskStatus[]> {
	const response = await api.get("/system/status/celery/tasks");
	return (response.data as Record<string, unknown>[]).map(
		transformCeleryTaskStatus,
	);
}

export async function refreshSystemStatus(): Promise<SystemStatusResponse> {
	const response = await api.post("/system/status/refresh");
	return transformSystemStatusResponse(response.data);
}
