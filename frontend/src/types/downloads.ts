// Types for the download client monitoring and control API.

export type TorrentGroup = "downloading" | "seeding" | "paused" | "queued";

export type TorrentStateValue =
	| "downloading"
	| "seeding"
	| "paused"
	| "checking"
	| "error"
	| "queued"
	| "completed";

export type ValidationResult =
	| "passed"
	| "failed_forbidden"
	| "failed_no_valid"
	| "pending";

export type ValidationStep =
	| "waiting_metadata"
	| "detecting_files"
	| "checking_extensions"
	| "resolving"
	| "passed"
	| "failed"
	| "pending";

export interface ValidationReport {
	result: ValidationResult;
	valid_files: string[];
	invalid_files: string[];
	forbidden_files: string[];
	total_files: number;
	valid_size: number;
	total_size: number;
	message: string;
}

export interface Torrent {
	hash: string;
	name: string;
	state: TorrentStateValue;
	group: TorrentGroup;
	progress: number; // 0..1
	download_speed: number;
	upload_speed: number;
	downloaded: number;
	uploaded: number;
	size: number;
	seeders: number;
	leechers: number;
	ratio: number;
	eta: number | null;
	save_path: string | null;
	category: string | null;
	tags: string[] | null;
	added_on: number | null;
	completion_on: number | null;
	ratio_limit: number;
	seeding_time: number;
	seeding_time_limit: number;
	inactive_seeding_time_limit: number;
	force_start: boolean;
	super_seeding: boolean;
	sequential_download: boolean;
	availability: number;
	num_complete: number;
	num_incomplete: number;
	dl_limit: number;
	up_limit: number;
	last_activity: number | null;
	tracker: string | null;
	// Merged Kinora history context
	media_id: number | null;
	media_type: string | null;
	media_title: string | null;
	indexer: string | null;
	quality: string | null;
	download_status: string | null;
	validation_step: ValidationStep | null;
	validation_report: ValidationReport | null;
}

export interface TorrentFile {
	name: string;
	size: number;
	progress: number;
	priority: number;
	availability?: number;
}

export interface TorrentTracker {
	url: string;
	status: number;
	tier?: number;
	num_peers?: number;
	num_seeds?: number;
	num_leeches?: number;
	msg?: string;
}

export interface TorrentDetail extends Torrent {
	files: TorrentFile[];
	trackers: TorrentTracker[];
	piece_states: number[]; // 0 = missing, 1 = downloading, 2 = downloaded
}

export interface TorrentsResponse {
	configured: boolean;
	torrents: Torrent[];
	unreachable?: boolean;
}

export interface DownloadStats {
	configured: boolean;
	unreachable?: boolean;
	download_speed?: number;
	upload_speed?: number;
	download_session_total?: number;
	upload_session_total?: number;
	download_rate_limit?: number;
	upload_rate_limit?: number;
	alt_speed_enabled?: boolean;
	connection_status?: string;
	dht_nodes?: number;
	counts?: {
		downloading: number;
		seeding: number;
		paused: number;
		queued: number;
		total: number;
	};
}

export interface ShareLimitsInput {
	ratio_limit: number;
	seeding_time_limit: number;
	inactive_seeding_time_limit: number;
}

export interface SpeedLimitsInput {
	download_limit: number;
	upload_limit: number;
}

export interface AddTorrentInput {
	url: string;
	media_type?: string;
	media_id?: number;
	category?: string;
	save_path?: string;
	tags?: string[];
}

export interface AutomationSettings {
	active_peer_pause_enabled: boolean;
	active_peer_pause_minutes: number;
	rare_seed_preserve_enabled: boolean;
	rare_seed_threshold: number;
	offpeak_enabled: boolean;
	offpeak_start_hour: number;
	offpeak_end_hour: number;
	offpeak_action: "alt_speed" | "pause";
	offpeak_days: number[];
	disk_pause_enabled: boolean;
	disk_min_free_gb: number;
	disk_min_free_unit: "gb" | "percent";
	auto_recovery_enabled: boolean;
	stall_timeout_minutes: number;
	seed_then_cleanup_enabled: boolean;
	gluetun_enabled: boolean;
	gluetun_url: string;
	vpn_kill_switch_enabled: boolean;
	vpn_port_sync_enabled: boolean;
	dl_limit_kbps: number;
	up_limit_kbps: number;
	alt_dl_limit_kbps: number;
	alt_up_limit_kbps: number;
}

export interface DownloadSettings {
	configured: boolean;
	seed_ratio_limit?: number | null;
	seed_time_limit?: number | null;
	inactive_seed_time_limit?: number | null;
	seed_action?: "pause" | "remove" | "remove_delete";
	allow_profile_seed_override?: boolean;
	automation: AutomationSettings;
	gluetun_api_key_set?: boolean;
}

export interface DownloadSettingsUpdate {
	seed_ratio_limit: number | null;
	seed_time_limit: number | null;
	inactive_seed_time_limit: number | null;
	seed_action: "pause" | "remove" | "remove_delete";
	allow_profile_seed_override: boolean;
	automation: AutomationSettings;
	gluetun_api_key?: string;
}

export interface IndexerSeedRule {
	id?: number;
	indexer: string;
	min_ratio: number;
	min_seed_minutes: number;
	enabled: boolean;
}

export interface ConnectionSafety {
	configured: boolean;
	source: "gluetun" | "heuristic" | "none";
	severity: "ok" | "warn" | "error";
	message: string;
	kinora_public_ip?: string | null;
	client_public_ip?: string | null;
	country?: string | null;
	city?: string | null;
	provider?: string | null;
	vpn_up?: boolean | null;
	forwarded_port?: number | null;
	interface_bound?: boolean | null;
	client_interface?: string | null;
	client_interface_address?: string | null;
}

export interface GluetunStatus {
	configured: boolean;
	running?: boolean;
	public_ip?: string | null;
	country?: string | null;
	city?: string | null;
	provider?: string | null;
	forwarded_port?: number | null;
	version?: string | null;
	message?: string | null;
}

export interface NetworkInterface {
	name: string;
	value: string;
}

export interface ImportQueueItem {
	id: number;
	torrent_hash: string;
	torrent_name: string | null;
	file_path: string;
	size: number | null;
	media_type: string | null;
	media_id: number | null;
	season_number: number | null;
	episode_number: number | null;
	root_folder_id: number | null;
	status: string;
	error_message: string | null;
	created_at: string;
}

export interface ResolveImportInput {
	media_id?: number;
	season_number?: number;
	episode_number?: number;
}

export interface TransferHistoryPoint {
	timestamp: string;
	download_speed: number;
	upload_speed: number;
	global_ratio: number;
	active_downloads: number;
	active_seeds: number;
}

export interface ImportSuggestion {
	media_id: number;
	title: string;
}

export interface ValidationPreview {
	validation_enabled: boolean;
	failure_action: string;
	allowed_extensions: string[];
	forbidden_extensions: string[];
	report: ValidationReport | null;
}

export interface ValidationPreviewInput {
	media_type: string;
	media_id?: number;
	profile_id?: number;
	files?: { name: string; size: number }[];
}

export interface SourceItem {
	id: number;
	torrent_title: string | null;
	media_type: string | null;
	media_id: number | null;
	indexer: string | null;
	quality: string | null;
	status: string | null;
	magnet_link: string | null;
	torrent_url: string | null;
	info_hash: string | null;
	indexer_page_url: string | null;
	torrent_hash: string | null;
	created_at: string;
}
