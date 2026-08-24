import api from "../api";
import type {
	TorrentsResponse,
	TorrentDetail,
	DownloadStats,
	ShareLimitsInput,
	SpeedLimitsInput,
	AddTorrentInput,
	DownloadSettings,
	DownloadSettingsUpdate,
	IndexerSeedRule,
	ConnectionSafety,
	GluetunStatus,
	NetworkInterface,
	ImportQueueItem,
	ResolveImportInput,
	SourceItem,
	ValidationPreview,
	ValidationPreviewInput,
	TransferHistoryPoint,
	ImportSuggestion,
} from "../../types/downloads";

export async function listTorrents(): Promise<TorrentsResponse> {
	const response = await api.get("/downloads/torrents");
	return response.data;
}

export async function getDownloadStats(): Promise<DownloadStats> {
	const response = await api.get("/downloads/stats");
	return response.data;
}

export async function getTorrentDetail(hash: string): Promise<TorrentDetail> {
	const response = await api.get(`/downloads/torrents/${hash}`);
	return response.data;
}

export async function pauseTorrent(hash: string): Promise<void> {
	await api.post(`/downloads/torrents/${hash}/pause`);
}

export async function resumeTorrent(hash: string): Promise<void> {
	await api.post(`/downloads/torrents/${hash}/resume`);
}

export async function recheckTorrent(hash: string): Promise<void> {
	await api.post(`/downloads/torrents/${hash}/recheck`);
}

export async function reannounceTorrent(hash: string): Promise<void> {
	await api.post(`/downloads/torrents/${hash}/reannounce`);
}

export async function setForceStart(
	hash: string,
	enabled: boolean,
): Promise<void> {
	await api.post(`/downloads/torrents/${hash}/force-start`, { enabled });
}

export async function setSuperSeeding(
	hash: string,
	enabled: boolean,
): Promise<void> {
	await api.post(`/downloads/torrents/${hash}/super-seeding`, { enabled });
}

export async function setSequentialDownload(
	hash: string,
	enabled: boolean,
): Promise<void> {
	await api.post(`/downloads/torrents/${hash}/sequential`, { enabled });
}

export async function queueAction(
	hash: string,
	action: "top" | "bottom" | "up" | "down",
): Promise<void> {
	await api.post(`/downloads/torrents/${hash}/queue`, { action });
}

export async function setTorrentShareLimits(
	hash: string,
	limits: ShareLimitsInput,
): Promise<void> {
	await api.put(`/downloads/torrents/${hash}/share-limits`, limits);
}

export async function setTorrentSpeedLimits(
	hash: string,
	limits: SpeedLimitsInput,
): Promise<void> {
	await api.put(`/downloads/torrents/${hash}/speed-limits`, limits);
}

export async function setGlobalSpeedLimits(
	limits: SpeedLimitsInput,
): Promise<void> {
	await api.put("/downloads/speed-limits", limits);
}

export async function toggleAltSpeed(): Promise<{
	alt_speed_enabled: boolean;
}> {
	const response = await api.post("/downloads/alt-speed/toggle");
	return response.data;
}

export async function deleteTorrent(
	hash: string,
	deleteFiles: boolean,
): Promise<void> {
	await api.delete(`/downloads/torrents/${hash}`, {
		params: { delete_files: deleteFiles },
	});
}

export async function addTorrent(
	input: AddTorrentInput,
): Promise<{ hash: string }> {
	const response = await api.post("/downloads/add", input);
	return response.data;
}

export async function getDownloadSettings(): Promise<DownloadSettings> {
	const response = await api.get("/downloads/settings");
	return response.data;
}

export async function updateDownloadSettings(
	body: DownloadSettingsUpdate,
): Promise<void> {
	await api.put("/downloads/settings", body);
}

export async function listIndexerRules(): Promise<IndexerSeedRule[]> {
	const response = await api.get("/downloads/indexer-rules");
	return response.data;
}

export async function upsertIndexerRule(
	rule: IndexerSeedRule,
): Promise<IndexerSeedRule> {
	const response = await api.put("/downloads/indexer-rules", rule);
	return response.data;
}

export async function deleteIndexerRule(id: number): Promise<void> {
	await api.delete(`/downloads/indexer-rules/${id}`);
}

export async function getConnectionSafety(): Promise<ConnectionSafety> {
	const response = await api.get("/downloads/connection-safety");
	return response.data;
}

export async function getGluetunStatus(): Promise<GluetunStatus> {
	const response = await api.get("/downloads/gluetun");
	return response.data;
}

export async function gluetunControl(
	action: "restart" | "stop" | "start",
): Promise<void> {
	await api.post(`/downloads/gluetun/${action}`);
}

export async function gluetunSyncPort(): Promise<{ port: number }> {
	const response = await api.post("/downloads/gluetun/sync-port");
	return response.data;
}

export async function getNetworkInterfaces(): Promise<NetworkInterface[]> {
	const response = await api.get("/downloads/interfaces");
	return response.data;
}

export async function setInterfaceBinding(
	iface: string,
	address: string,
): Promise<void> {
	await api.post("/downloads/interface-binding", {
		interface: iface,
		address,
	});
}

export async function listImportQueue(): Promise<ImportQueueItem[]> {
	const response = await api.get("/downloads/import");
	return response.data;
}

export async function resolveImport(
	id: number,
	input: ResolveImportInput,
): Promise<void> {
	await api.post(`/downloads/import/${id}/resolve`, input);
}

export async function dismissImport(id: number): Promise<void> {
	await api.delete(`/downloads/import/${id}`);
}

export async function listSources(search?: string): Promise<SourceItem[]> {
	const response = await api.get("/downloads/sources", {
		params: search ? { search } : {},
	});
	return response.data;
}

export async function reAddSource(id: number): Promise<{ hash: string }> {
	const response = await api.post(`/downloads/sources/${id}/re-add`);
	return response.data;
}

export async function getValidationPreview(
	input: ValidationPreviewInput,
): Promise<ValidationPreview> {
	const response = await api.post("/downloads/validate-preview", input);
	return response.data;
}

export async function getTransferHistory(
	hours: number,
): Promise<TransferHistoryPoint[]> {
	const response = await api.get("/downloads/history-stats", {
		params: { hours },
	});
	return response.data;
}

export async function suggestImportMatches(
	itemId: number,
): Promise<ImportSuggestion[]> {
	const response = await api.get(`/downloads/import/${itemId}/suggest`);
	return response.data;
}
