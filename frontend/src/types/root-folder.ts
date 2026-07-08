export type MediaType = "movies" | "shows" | "anime" | "music";
export type SelectionMode = "most_free_space" | "priority" | "fill_threshold";
export type HealthStatus = "healthy" | "warning" | "error" | "unknown";

export interface RootFolder {
	id: number;
	mediaType: MediaType;
	name: string;
	rootPath: string;
	downloadPath: string;
	priority: number;
	fillThresholdPercent: number | null;
	fillThresholdGb: number | null;
	isActive: boolean;
	isDefault: boolean;
	totalSpaceBytes: number | null;
	freeSpaceBytes: number | null;
	usedSpaceBytes: number | null;
	usedPercent: number | null;
	lastHealthCheck: string | null;
	healthStatus: HealthStatus;
	healthMessage: string | null;
	createdAt: string;
	updatedAt: string;
}

export interface FolderSelectionSettings {
	id: number;
	mediaType: MediaType;
	selectionMode: SelectionMode;
	createdAt: string | null;
	updatedAt: string | null;
}

export interface CreateRootFolderRequest {
	mediaType: MediaType;
	name: string;
	rootPath: string;
	downloadPath?: string;
	priority?: number;
	fillThresholdPercent?: number;
	fillThresholdGb?: number;
}

export interface UpdateRootFolderRequest {
	name?: string;
	rootPath?: string;
	downloadPath?: string;
	priority?: number;
	fillThresholdPercent?: number;
	fillThresholdGb?: number;
	isActive?: boolean;
}

export interface FolderTestResult {
	success: boolean;
	rootPathAccessible: boolean;
	rootPathWritable: boolean;
	downloadPathAccessible: boolean;
	downloadPathWritable: boolean;
	sameFilesystem: boolean;
	hardlinkSupported: boolean;
	message: string | null;
}

export interface DriveStats {
	drive: string;
	totalBytes: number;
	usedBytes: number;
	freeBytes: number;
	usedPercent: number;
	folderCount: number;
	folders: RootFolder[];
}

export interface FolderHealthSummary {
	totalFolders: number;
	healthyCount: number;
	warningCount: number;
	errorCount: number;
	unknownCount: number;
}

export interface BrowseDirectoryResponse {
	path: string;
	parent: string | null;
	directories: string[];
	isRoot: boolean;
}
