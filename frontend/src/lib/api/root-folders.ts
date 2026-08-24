import api from "../api";
import type {
	RootFolder,
	FolderSelectionSettings,
	CreateRootFolderRequest,
	UpdateRootFolderRequest,
	FolderTestResult,
	DriveStats,
	FolderHealthSummary,
	BrowseDirectoryResponse,
	MediaType,
	SelectionMode,
} from "../../types/root-folder";

// Helper to convert snake_case API response to camelCase
function transformFolder(data: Record<string, unknown>): RootFolder {
	return {
		id: data.id as number,
		mediaType: data.media_type as MediaType,
		name: data.name as string,
		rootPath: data.root_path as string,
		downloadPath: data.download_path as string,
		priority: data.priority as number,
		fillThresholdPercent: data.fill_threshold_percent as number | null,
		fillThresholdGb: data.fill_threshold_gb as number | null,
		isActive: data.is_active as boolean,
		isDefault: (data.is_default as boolean) ?? false,
		totalSpaceBytes: data.total_space_bytes as number | null,
		freeSpaceBytes: data.free_space_bytes as number | null,
		usedSpaceBytes: data.used_space_bytes as number | null,
		usedPercent: data.used_percent as number | null,
		lastHealthCheck: data.last_health_check as string | null,
		healthStatus:
			(data.health_status as RootFolder["healthStatus"]) || "unknown",
		healthMessage: data.health_message as string | null,
		createdAt: data.created_at as string,
		updatedAt: data.updated_at as string,
	};
}

export async function getRootFolders(
	mediaType?: MediaType,
): Promise<RootFolder[]> {
	const params = mediaType ? { mediaType } : {};
	const response = await api.get("/root-folders", { params });
	return response.data.map(transformFolder);
}

export async function getRootFolder(id: number): Promise<RootFolder> {
	const response = await api.get(`/root-folders/${id}`);
	return transformFolder(response.data);
}

export async function createRootFolder(
	data: CreateRootFolderRequest,
): Promise<RootFolder> {
	const payload = {
		media_type: data.mediaType,
		name: data.name,
		root_path: data.rootPath,
		download_path: data.downloadPath,
		priority: data.priority,
		fill_threshold_percent: data.fillThresholdPercent,
		fill_threshold_gb: data.fillThresholdGb,
	};
	const response = await api.post("/root-folders", payload);
	return transformFolder(response.data);
}

export async function updateRootFolder(
	id: number,
	data: UpdateRootFolderRequest,
): Promise<RootFolder> {
	const payload: Record<string, unknown> = {};
	if (data.name !== undefined) payload.name = data.name;
	if (data.rootPath !== undefined) payload.root_path = data.rootPath;
	if (data.downloadPath !== undefined)
		payload.download_path = data.downloadPath;
	if (data.priority !== undefined) payload.priority = data.priority;
	if (data.fillThresholdPercent !== undefined)
		payload.fill_threshold_percent = data.fillThresholdPercent;
	if (data.fillThresholdGb !== undefined)
		payload.fill_threshold_gb = data.fillThresholdGb;
	if (data.isActive !== undefined) payload.is_active = data.isActive;

	const response = await api.put(`/root-folders/${id}`, payload);
	return transformFolder(response.data);
}

export async function deleteRootFolder(id: number): Promise<void> {
	await api.delete(`/root-folders/${id}`);
}

export async function testRootFolder(id: number): Promise<FolderTestResult> {
	const response = await api.post(`/root-folders/${id}/test`);
	const data = response.data;
	return {
		success: data.success,
		rootPathAccessible: data.root_path_accessible,
		rootPathWritable: data.root_path_writable,
		downloadPathAccessible: data.download_path_accessible,
		downloadPathWritable: data.download_path_writable,
		sameFilesystem: data.same_filesystem,
		hardlinkSupported: data.hardlink_supported,
		message: data.message,
	};
}

export async function testFolderPaths(
	rootPath: string,
	downloadPath?: string,
): Promise<FolderTestResult> {
	const response = await api.post("/root-folders/test", {
		root_path: rootPath,
		download_path: downloadPath,
	});
	const data = response.data;
	return {
		success: data.success,
		rootPathAccessible: data.root_path_accessible,
		rootPathWritable: data.root_path_writable,
		downloadPathAccessible: data.download_path_accessible,
		downloadPathWritable: data.download_path_writable,
		sameFilesystem: data.same_filesystem,
		hardlinkSupported: data.hardlink_supported,
		message: data.message,
	};
}

export async function refreshFolderHealth(id: number): Promise<void> {
	await api.post(`/root-folders/${id}/refresh-health`);
}

export async function getHealthSummary(): Promise<FolderHealthSummary> {
	const response = await api.get("/root-folders/health");
	const data = response.data;
	return {
		totalFolders: data.total_folders,
		healthyCount: data.healthy_count,
		warningCount: data.warning_count,
		errorCount: data.error_count,
		unknownCount: data.unknown_count,
	};
}

export async function getDriveStats(): Promise<DriveStats[]> {
	const response = await api.get("/root-folders/drives");
	return response.data.map((drive: Record<string, unknown>) => ({
		drive: drive.drive as string,
		totalBytes: drive.total_bytes as number,
		usedBytes: drive.used_bytes as number,
		freeBytes: drive.free_bytes as number,
		usedPercent: drive.used_percent as number,
		folderCount: drive.folder_count as number,
		folders: (drive.folders as Record<string, unknown>[]).map(
			transformFolder,
		),
	}));
}

export async function getSelectionSettings(
	mediaType: MediaType,
): Promise<FolderSelectionSettings> {
	const response = await api.get(
		`/root-folders/selection-settings/${mediaType}`,
	);
	const data = response.data;
	return {
		id: data.id,
		mediaType: data.media_type,
		selectionMode: data.selection_mode,
		createdAt: data.created_at,
		updatedAt: data.updated_at,
	};
}

export async function updateSelectionSettings(
	mediaType: MediaType,
	selectionMode: SelectionMode,
): Promise<FolderSelectionSettings> {
	const response = await api.put(
		`/root-folders/selection-settings/${mediaType}`,
		{
			selection_mode: selectionMode,
		},
	);
	const data = response.data;
	return {
		id: data.id,
		mediaType: data.media_type,
		selectionMode: data.selection_mode,
		createdAt: data.created_at,
		updatedAt: data.updated_at,
	};
}

export async function browseDirectory(
	path?: string,
): Promise<BrowseDirectoryResponse> {
	const response = await api.post("/root-folders/browse", { path });
	const data = response.data;
	return {
		path: data.path,
		parent: data.parent,
		directories: data.directories,
		isRoot: data.is_root,
	};
}
