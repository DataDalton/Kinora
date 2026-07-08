"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import {
	X,
	Search,
	Download,
	Loader2,
	HardDrive,
	Users,
	Clock,
	Filter,
	SortAsc,
	SortDesc,
	ChevronDown,
	User,
	ShieldCheck,
} from "lucide-react";
import Toast from "./Toast";
import { getValidationPreview } from "@/lib/api/downloads";

interface TorrentResult {
	title: string;
	size: number;
	seeders: number;
	leechers: number;
	quality: string;
	source: string;
	indexer: string;
	indexer_page_url: string;
	torrent_url: string;
	magnet_link: string;
	info_hash: string;
	upload_date: string;
	uploader: string;
}

interface IndexerStatus {
	name: string;
	status: "success" | "error";
	count?: number;
	error?: string;
}

interface SearchResponse {
	results: TorrentResult[];
	indexers?: IndexerStatus[];
}

interface SearchOptions {
	all_options: {
		resolutions: string[];
		sources: string[];
		codecs: string[];
		audio_codecs: string[];
		audio_channels: string[];
		hdr: string[];
	};
	available_indexers: string[];
	profile: {
		id: number | null;
		name: string | null;
		resolutions: string[];
		indexers: string[];
	} | null;
}

interface InteractiveSearchModalProps {
	isOpen: boolean;
	onClose: () => void;
	mediaType: "movie" | "show" | "anime" | "album" | "track";
	// Null when the item is not in the library yet (deferred add). ensureMediaId creates
	// it on the first grab and returns its id.
	mediaId: number | null;
	mediaTitle: string;
	searchQuery?: string;
	episodeId?: number;
	episodeInfo?: string;
	// Creates the library item on demand (first grab) and returns its id, or null on
	// failure. When absent, mediaId must already be set.
	ensureMediaId?: () => Promise<number | null>;
	// Profile to score/validate against while no item exists yet (deferred add).
	profileId?: number | null;
	// Provided in the deferred-add flow to let the user pick the profile from the search.
	// Updating it changes which profile the item is created with on download.
	onProfileChange?: (id: number | null) => void;
}

type SortField = "seeders" | "size" | "upload_date" | "quality";
type SortDirection = "asc" | "desc";

const formatSize = (bytes: number): string => {
	if (bytes === 0) return "0 B";
	const k = 1024;
	const sizes = ["B", "KB", "MB", "GB", "TB"];
	const i = Math.floor(Math.log(bytes) / Math.log(k));
	return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
};

const qualityOrder: Record<string, number> = {
	"2160p": 1,
	"4K": 1,
	"1080p": 2,
	"720p": 3,
	"480p": 4,
	HDTV: 5,
	SDTV: 6,
	Unknown: 7,
};

// True when the text is a magnet link or a direct .torrent URL rather than a search term.
const isMagnetOrTorrentUrl = (input: string): boolean => {
	const t = input.trim().toLowerCase();
	return (
		t.startsWith("magnet:?") || /^https?:\/\/\S+\.torrent(\?\S*)?$/.test(t)
	);
};

const parseQualityFromTitle = (title: string): string => {
	const t = title.toLowerCase();
	if (t.includes("2160p") || t.includes("4k") || t.includes("uhd"))
		return "2160p";
	if (t.includes("1080p")) return "1080p";
	if (t.includes("720p")) return "720p";
	if (t.includes("480p")) return "480p";
	return "Unknown";
};

// Turn a pasted magnet/.torrent URL into a single grabbable result. The title (and any
// quality) come from the magnet display name; size/seeders are unknown until it downloads.
const buildManualRelease = (input: string): TorrentResult => {
	const trimmed = input.trim();
	const isMagnet = trimmed.toLowerCase().startsWith("magnet:");
	let title = "Manual link";
	let infoHash = "";
	if (isMagnet) {
		const params = new URLSearchParams(
			trimmed.slice(trimmed.indexOf("?") + 1),
		);
		const xt = params.get("xt") || "";
		const hashMatch = xt.match(/urn:btih:([a-z0-9]+)/i);
		if (hashMatch) infoHash = hashMatch[1];
		const dn = params.get("dn");
		title = dn || infoHash || "Magnet link";
	} else {
		try {
			title = decodeURIComponent(
				trimmed.split("/").pop() || "Torrent file",
			);
		} catch {
			title = "Torrent file";
		}
	}
	return {
		title,
		size: 0,
		seeders: 0,
		leechers: 0,
		quality: parseQualityFromTitle(title),
		source: "",
		indexer: "Manual",
		indexer_page_url: "",
		torrent_url: isMagnet ? "" : trimmed,
		magnet_link: isMagnet ? trimmed : "",
		info_hash: infoHash,
		upload_date: "",
		uploader: "",
	};
};

export default function InteractiveSearchModal({
	isOpen,
	onClose,
	mediaType,
	mediaId,
	mediaTitle,
	searchQuery: initialSearchQuery,
	episodeId,
	episodeInfo,
	ensureMediaId,
	profileId,
	onProfileChange,
}: InteractiveSearchModalProps) {
	const queryClient = useQueryClient();
	// Resolved library-item id. Starts from the prop and is filled in by ensureMediaId on
	// the first grab when the item is added lazily.
	const [effectiveMediaId, setEffectiveMediaId] = useState<number | null>(
		mediaId,
	);
	const [searchQuery, setSearchQuery] = useState(
		initialSearchQuery || mediaTitle,
	);
	const [sortField, setSortField] = useState<SortField>("seeders");
	const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
	const [qualityFilter, setQualityFilter] = useState<string>("all");
	const [indexerFilter, setIndexerFilter] = useState<string>("all");
	const [showFilters, setShowFilters] = useState(false);
	const [toast, setToast] = useState<{
		message: string;
		type: "success" | "error" | "info";
	} | null>(null);
	const [indexerStatus, setIndexerStatus] = useState<IndexerStatus[]>([]);
	const [selectedIndexers, setSelectedIndexers] = useState<string[]>([]);
	const [selectedQuality, setSelectedQuality] = useState<string>("all");
	const [showValidation, setShowValidation] = useState(false);
	// A pasted magnet / .torrent URL shown as a single grabbable result instead of running
	// an indexer search. Cleared when a normal text search runs or the modal reopens.
	const [manualRelease, setManualRelease] = useState<TorrentResult | null>(
		null,
	);
	// Monitoring decision applied by the last manual grab (movie/show/anime). Backed by a
	// one-click override that flips the item between satisfied and keep-monitoring.
	const [grabMonitoringMode, setGrabMonitoringMode] = useState<
		"satisfied" | "monitoring" | null
	>(null);
	// Release awaiting the pre-grab satisfied/keep-monitoring confirmation, plus the chosen mode.
	const [pendingGrab, setPendingGrab] = useState<TorrentResult | null>(null);
	const [pendingChoice, setPendingChoice] = useState<
		"satisfied" | "monitoring"
	>("monitoring");

	// Preview the validation rules that will apply to a grab from this media's profile.
	// Tracks are validated under their album/music profile rules.
	const previewMediaType = mediaType === "track" ? "album" : mediaType;
	const { data: validationPreview } = useQuery({
		queryKey: [
			"validation-preview",
			previewMediaType,
			effectiveMediaId,
			profileId,
		],
		queryFn: () =>
			getValidationPreview(
				effectiveMediaId != null
					? {
							media_type: previewMediaType,
							media_id: effectiveMediaId,
						}
					: {
							media_type: previewMediaType,
							profile_id: profileId ?? undefined,
						},
			),
		// With no item and no profile there is nothing to validate against.
		enabled: isOpen && (effectiveMediaId != null || profileId != null),
	});

	// Fetch available options from backend. Before an item exists (deferred add) pass the
	// chosen profile so its indexers/resolutions still apply; media_id 0 is a no-op lookup.
	const { data: searchOptions } = useQuery({
		queryKey: ["search-options", mediaType, effectiveMediaId, profileId],
		queryFn: async () => {
			const response = await api.get(
				`/search/options/${mediaType}/${effectiveMediaId ?? 0}`,
				{
					params:
						effectiveMediaId == null && profileId != null
							? { profile_id: profileId }
							: undefined,
				},
			);
			return response.data as SearchOptions;
		},
		enabled: isOpen,
	});

	// In the deferred-add flow the item does not exist yet, so let the user pick the media
	// profile right here. It drives validation/indexers and the profile the item is created
	// with on download. For an existing library item the profile is fixed, so no picker.
	const showProfilePicker = effectiveMediaId == null && !!onProfileChange;
	const { data: profileList } = useQuery({
		queryKey: ["media-profiles"],
		queryFn: async () => {
			const response = await api.get("/media-profiles");
			return response.data as { id: number; name: string }[];
		},
		enabled: isOpen && showProfilePicker,
	});

	// Initialize selected indexers from profile or defaults
	useEffect(() => {
		if (searchOptions) {
			const profileIndexers = searchOptions.profile?.indexers || [];
			const availableIndexers = searchOptions.available_indexers || [];
			// Use profile indexers if set, otherwise use all available
			if (profileIndexers.length > 0) {
				setSelectedIndexers(
					profileIndexers.filter((i) =>
						availableIndexers.includes(i),
					),
				);
			} else {
				setSelectedIndexers(availableIndexers);
			}
		}
	}, [searchOptions]);

	const showToast = (message: string, type: "success" | "error" | "info") => {
		setToast(null);
		setTimeout(() => setToast({ message, type }), 0);
	};

	useEffect(() => {
		if (isOpen) {
			setSearchQuery(mediaTitle);
			setGrabMonitoringMode(null);
			setEffectiveMediaId(mediaId);
			setManualRelease(null);
			setPendingGrab(null);
		}
	}, [isOpen, mediaTitle, mediaId]);

	// Keep the resolved id in sync if the parent supplies one after mount.
	useEffect(() => {
		if (mediaId != null) {
			setEffectiveMediaId(mediaId);
		}
	}, [mediaId]);

	useEffect(() => {
		const handleEscape = (e: KeyboardEvent) => {
			if (e.key === "Escape" && isOpen) {
				onClose();
			}
		};
		document.addEventListener("keydown", handleEscape);
		return () => document.removeEventListener("keydown", handleEscape);
	}, [isOpen, onClose]);

	const {
		data: searchResults,
		isLoading,
		refetch,
		isFetching,
	} = useQuery({
		queryKey: [
			"interactive-search",
			mediaType,
			searchQuery,
			selectedIndexers,
			selectedQuality,
		],
		queryFn: async () => {
			const response = await api.post("/search/interactive", {
				query: searchQuery,
				media_type: mediaType,
				media_id: effectiveMediaId,
				episode_id: episodeId,
				indexers: selectedIndexers.length > 0 ? selectedIndexers : null,
				quality: selectedQuality !== "all" ? selectedQuality : null,
			});
			const data = response.data as SearchResponse;
			if (data.indexers) {
				setIndexerStatus(data.indexers);
			}
			return data.results;
		},
		enabled: false,
	});

	const downloadMutation = useMutation({
		mutationFn: async ({
			result,
			keepMonitoring,
		}: {
			result: TorrentResult;
			keepMonitoring?: boolean;
		}) => {
			// Resolve the target item, creating it now if the add was deferred until download.
			let targetId = effectiveMediaId;
			if (targetId == null && ensureMediaId) {
				targetId = await ensureMediaId();
				if (targetId != null) {
					setEffectiveMediaId(targetId);
				}
			}
			if (targetId == null) {
				throw new Error("Could not add this item to your library");
			}
			const response = await api.post("/search/download-release", {
				torrent_url: result.torrent_url,
				magnet_link: result.magnet_link,
				media_type: mediaType,
				media_id: targetId,
				episode_id: episodeId,
				indexer: result.indexer,
				indexer_page_url: result.indexer_page_url,
				title: result.title,
				quality: result.quality,
				size: result.size,
				seeders: result.seeders,
				// Chosen before the grab: TRUE keeps monitoring for upgrades, FALSE marks the item
				// satisfied. Undefined lets the backend decide from the profile score.
				keep_monitoring: keepMonitoring,
			});
			return response.data;
		},
		onSuccess: (data) => {
			let message = "Download started successfully";
			if (data?.monitoring_mode === "satisfied") {
				message = "Grabbed and marked satisfied (will not upgrade)";
				setGrabMonitoringMode("satisfied");
			} else if (data?.monitoring_mode === "monitoring") {
				message = "Grabbed, keeping monitored for upgrades";
				setGrabMonitoringMode("monitoring");
			}
			showToast(message, "success");
			queryClient.invalidateQueries({ queryKey: ["history"] });
		},
		onError: (error: any) => {
			// Axios errors carry response.data.detail; guard failures (permission/approval) throw
			// a plain Error whose message explains why the item could not be added.
			showToast(
				error.response?.data?.detail ||
					error.message ||
					"Failed to start download",
				"error",
			);
		},
	});

	// Endpoint that owns this item's monitoring/upgrade flag. Mirrors MonitoringOptionsDropdown:
	// music types live under /music, anime is singular, movies/shows are plural.
	const monitoringEndpoint = () => {
		if (mediaType === "album" || mediaType === "track") {
			return `/music/${mediaType}s/${effectiveMediaId}/monitoring`;
		}
		if (mediaType === "anime") {
			return `/anime/${effectiveMediaId}/monitoring`;
		}
		return `/${mediaType}s/${effectiveMediaId}/monitoring`;
	};

	// One-click override of the post-grab monitoring decision. satisfied => upgrade_allowed
	// FALSE (stop searching); monitoring => TRUE (keep searching for upgrades).
	const overrideMonitoringMutation = useMutation({
		mutationFn: async (nextMode: "satisfied" | "monitoring") => {
			await api.put(monitoringEndpoint(), {
				upgradeAllowed: nextMode === "monitoring",
			});
			return nextMode;
		},
		onSuccess: (nextMode) => {
			setGrabMonitoringMode(nextMode);
			queryClient.invalidateQueries({
				queryKey: [mediaType, effectiveMediaId],
			});
			showToast(
				nextMode === "monitoring"
					? "Now keeping monitored for upgrades"
					: "Marked satisfied (will not upgrade)",
				"success",
			);
		},
		onError: (error: any) => {
			showToast(
				error.response?.data?.detail || "Failed to update monitoring",
				"error",
			);
		},
	});

	const handleSearch = () => {
		const trimmed = searchQuery.trim();
		if (!trimmed) return;
		// A pasted magnet / .torrent URL is grabbed directly rather than searched for.
		if (isMagnetOrTorrentUrl(trimmed)) {
			setManualRelease(buildManualRelease(trimmed));
			return;
		}
		setManualRelease(null);
		refetch();
	};

	const handleKeyPress = (e: React.KeyboardEvent) => {
		if (e.key === "Enter") {
			handleSearch();
		}
	};

	const sortResults = (results: TorrentResult[]): TorrentResult[] => {
		return [...results].sort((a, b) => {
			let comparison = 0;
			switch (sortField) {
				case "seeders":
					comparison = a.seeders - b.seeders;
					break;
				case "size":
					comparison = a.size - b.size;
					break;
				case "upload_date":
					comparison =
						new Date(a.upload_date).getTime() -
						new Date(b.upload_date).getTime();
					break;
				case "quality":
					comparison =
						(qualityOrder[a.quality] || 99) -
						(qualityOrder[b.quality] || 99);
					break;
			}
			return sortDirection === "desc" ? -comparison : comparison;
		});
	};

	const filterResults = (results: TorrentResult[]): TorrentResult[] => {
		return results.filter((r) => {
			if (qualityFilter !== "all" && r.quality !== qualityFilter)
				return false;
			if (indexerFilter !== "all" && r.indexer !== indexerFilter)
				return false;
			return true;
		});
	};

	const processedResults = searchResults
		? sortResults(filterResults(searchResults))
		: [];
	// A pasted magnet / .torrent URL shows as the only result; otherwise show indexer results.
	const displayResults = manualRelease ? [manualRelease] : processedResults;
	// The satisfied/keep-monitoring choice is only honored by the backend for these types, so
	// only they get the pre-grab confirmation; others grab directly.
	const monitoringApplies = ["movie", "show", "anime", "album"].includes(
		mediaType,
	);

	// Start a grab: confirm the satisfied/keep-monitoring choice first where it applies.
	const startGrab = (result: TorrentResult) => {
		if (monitoringApplies) {
			setPendingChoice("monitoring");
			setPendingGrab(result);
		} else {
			downloadMutation.mutate({ result });
		}
	};

	// Get quality options from backend (resolutions)
	const qualityOptions = searchOptions?.all_options?.resolutions ?? [];
	// Get available indexers from backend
	const availableIndexers = searchOptions?.available_indexers ?? [];

	// Toggle indexer selection
	const toggleIndexer = (indexer: string) => {
		setSelectedIndexers((prev) =>
			prev.includes(indexer)
				? prev.filter((i) => i !== indexer)
				: [...prev, indexer],
		);
	};

	if (!isOpen) return null;

	return (
		<div className="fixed inset-0 backdrop-blur-sm bg-background/50 z-[60] flex items-center justify-center p-4">
			<div className="bg-background rounded-lg w-full max-w-5xl max-h-[90vh] border border-border shadow-2xl flex flex-col">
				<div className="flex items-center justify-between p-4 border-b border-border">
					<div>
						<h2 className="text-xl font-bold">
							Interactive Search
						</h2>
						<p className="text-sm text-muted-foreground">
							{mediaTitle}
							{episodeInfo && (
								<span className="ml-2">{episodeInfo}</span>
							)}
						</p>
					</div>
					<button
						onClick={onClose}
						className="p-2 hover:bg-muted rounded-lg transition cursor-pointer"
					>
						<X className="w-5 h-5" />
					</button>
				</div>

				<div className="p-4 border-b border-border space-y-3">
					{showProfilePicker && (
						<div className="flex items-center gap-2">
							<label className="text-sm text-muted-foreground whitespace-nowrap">
								Media profile:
							</label>
							<select
								value={profileId ?? ""}
								onChange={(e) =>
									onProfileChange?.(
										e.target.value
											? Number(e.target.value)
											: null,
									)
								}
								className="px-3 py-1.5 bg-muted border border-border rounded-lg text-sm cursor-pointer"
							>
								<option value="">No profile</option>
								{(profileList ?? []).map((p) => (
									<option key={p.id} value={p.id}>
										{p.name}
									</option>
								))}
							</select>
						</div>
					)}
					<div className="flex gap-2">
						<div className="flex-1 relative">
							<Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-muted-foreground" />
							<input
								type="text"
								value={searchQuery}
								onChange={(e) => setSearchQuery(e.target.value)}
								onKeyPress={handleKeyPress}
								placeholder="Search for releases, or paste a magnet / .torrent URL"
								className="w-full pl-10 pr-4 py-2 bg-muted border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
							/>
						</div>
						<button
							onClick={handleSearch}
							disabled={isLoading || isFetching}
							className="px-6 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
						>
							{isLoading || isFetching ? (
								<Loader2 className="w-5 h-5 animate-spin" />
							) : isMagnetOrTorrentUrl(searchQuery) ? (
								<Download className="w-5 h-5" />
							) : (
								<Search className="w-5 h-5" />
							)}
							{isMagnetOrTorrentUrl(searchQuery)
								? "Load link"
								: "Search"}
						</button>
						<button
							onClick={() => setShowFilters(!showFilters)}
							className={`px-4 py-2 rounded-lg transition cursor-pointer flex items-center gap-2 ${
								showFilters
									? "bg-primary text-primary-foreground"
									: "bg-muted hover:bg-muted/80"
							}`}
						>
							<Filter className="w-5 h-5" />
							<ChevronDown
								className={`w-4 h-4 transition ${showFilters ? "rotate-180" : ""}`}
							/>
						</button>
						<button
							onClick={() => setShowValidation(!showValidation)}
							title="Validation rules preview"
							className={`px-4 py-2 rounded-lg transition cursor-pointer flex items-center gap-2 ${
								showValidation
									? "bg-primary text-primary-foreground"
									: "bg-muted hover:bg-muted/80"
							}`}
						>
							<ShieldCheck className="w-5 h-5" />
							<ChevronDown
								className={`w-4 h-4 transition ${showValidation ? "rotate-180" : ""}`}
							/>
						</button>
					</div>

					{showValidation && (
						<div className="rounded-lg border border-border bg-muted/40 p-3 text-sm space-y-2">
							{!validationPreview ? (
								<p className="text-xs text-muted-foreground">
									{effectiveMediaId != null ||
									profileId != null
										? "Loading validation rules..."
										: "Select a media profile above to preview its validation rules."}
								</p>
							) : validationPreview.validation_enabled ? (
								<>
									<div className="flex flex-wrap items-center gap-3 text-xs">
										<span className="flex items-center gap-1 text-green-500">
											<ShieldCheck className="w-3.5 h-3.5" />{" "}
											Validation on
										</span>
										<span className="text-muted-foreground">
											On failure:{" "}
											<span className="text-foreground">
												{validationPreview.failure_action.replace(
													"_",
													" & ",
												)}
											</span>
										</span>
									</div>
									<div>
										<p className="text-xs font-medium text-muted-foreground mb-1">
											Allowed file types
										</p>
										<div className="flex flex-wrap gap-1">
											{validationPreview.allowed_extensions.map(
												(ext) => (
													<span
														key={ext}
														className="px-2 py-0.5 rounded bg-green-500/15 text-green-500 text-xs"
													>
														{ext}
													</span>
												),
											)}
										</div>
									</div>
									<div>
										<p className="text-xs font-medium text-muted-foreground mb-1">
											Blocked file types
										</p>
										<div className="flex flex-wrap gap-1">
											{validationPreview.forbidden_extensions.map(
												(ext) => (
													<span
														key={ext}
														className="px-2 py-0.5 rounded bg-destructive/15 text-destructive text-xs"
													>
														{ext}
													</span>
												),
											)}
										</div>
									</div>
									<p className="text-xs text-muted-foreground">
										After grabbing, the torrent is paused
										until its files are checked against
										these rules.
									</p>
								</>
							) : (
								<p className="text-xs text-muted-foreground">
									Validation is disabled for this profile.
									Grabs start immediately without a file-type
									check.
								</p>
							)}
						</div>
					)}

					{showFilters && (
						<div className="space-y-3 pt-2">
							{/* Search filters - these affect what is searched */}
							<div className="flex flex-wrap gap-4">
								<div className="flex items-center gap-2">
									<label className="text-sm text-muted-foreground">
										Quality:
									</label>
									<select
										value={selectedQuality}
										onChange={(e) =>
											setSelectedQuality(e.target.value)
										}
										className="px-3 py-1.5 bg-muted border border-border rounded-lg text-sm cursor-pointer"
									>
										<option value="all">All</option>
										{qualityOptions.map((q) => (
											<option key={q} value={q}>
												{q}
											</option>
										))}
									</select>
								</div>
								<div className="flex items-center gap-2">
									<label className="text-sm text-muted-foreground">
										Indexers:
									</label>
									<div className="flex flex-wrap gap-1">
										{availableIndexers.map((indexer) => (
											<button
												key={indexer}
												onClick={() =>
													toggleIndexer(indexer)
												}
												className={`px-2 py-1 text-xs rounded transition cursor-pointer ${
													selectedIndexers.includes(
														indexer,
													)
														? "bg-primary text-primary-foreground"
														: "bg-muted hover:bg-muted/80 text-muted-foreground"
												}`}
											>
												{indexer}
											</button>
										))}
									</div>
								</div>
							</div>
							{/* Result sorting and filtering */}
							<div className="flex flex-wrap gap-4">
								<div className="flex items-center gap-2">
									<label className="text-sm text-muted-foreground">
										Filter results:
									</label>
									<select
										value={qualityFilter}
										onChange={(e) =>
											setQualityFilter(e.target.value)
										}
										className="px-3 py-1.5 bg-muted border border-border rounded-lg text-sm cursor-pointer"
									>
										<option value="all">
											All qualities
										</option>
										{qualityOptions.map((q) => (
											<option key={q} value={q}>
												{q}
											</option>
										))}
									</select>
									<select
										value={indexerFilter}
										onChange={(e) =>
											setIndexerFilter(e.target.value)
										}
										className="px-3 py-1.5 bg-muted border border-border rounded-lg text-sm cursor-pointer"
									>
										<option value="all">
											All indexers
										</option>
										{availableIndexers.map((i) => (
											<option key={i} value={i}>
												{i}
											</option>
										))}
									</select>
								</div>
								<div className="flex items-center gap-2">
									<label className="text-sm text-muted-foreground">
										Sort by:
									</label>
									<select
										value={sortField}
										onChange={(e) =>
											setSortField(
												e.target.value as SortField,
											)
										}
										className="px-3 py-1.5 bg-muted border border-border rounded-lg text-sm cursor-pointer"
									>
										<option value="seeders">Seeders</option>
										<option value="size">Size</option>
										<option value="quality">Quality</option>
										<option value="upload_date">
											Date
										</option>
									</select>
									<button
										onClick={() =>
											setSortDirection(
												sortDirection === "asc"
													? "desc"
													: "asc",
											)
										}
										className="p-1.5 bg-muted rounded-lg hover:bg-muted/80 transition cursor-pointer"
									>
										{sortDirection === "desc" ? (
											<SortDesc className="w-4 h-4" />
										) : (
											<SortAsc className="w-4 h-4" />
										)}
									</button>
								</div>
							</div>
						</div>
					)}

					{indexerStatus.length > 0 && (
						<div className="flex flex-wrap gap-2 pt-2">
							{indexerStatus.map((indexer) => (
								<div
									key={indexer.name}
									className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs ${
										indexer.status === "success"
											? "bg-green-500/20 text-green-500"
											: "bg-destructive/20 text-destructive"
									}`}
									title={
										indexer.error ||
										`${indexer.count} results`
									}
								>
									<span
										className={`w-1.5 h-1.5 rounded-full ${
											indexer.status === "success"
												? "bg-green-500"
												: "bg-destructive"
										}`}
									/>
									{indexer.name}
									{indexer.status === "success" &&
										indexer.count !== undefined && (
											<span className="text-muted-foreground">
												({indexer.count})
											</span>
										)}
									{indexer.status === "error" &&
										indexer.error && (
											<span className="text-muted-foreground">
												- {indexer.error}
											</span>
										)}
								</div>
							))}
						</div>
					)}
				</div>

				{grabMonitoringMode && (
					<div className="mx-4 mt-3 flex items-center justify-between gap-3 rounded-lg border border-border bg-muted/50 px-4 py-2 text-sm">
						<span className="text-muted-foreground">
							{grabMonitoringMode === "satisfied"
								? "Grabbed release meets this profile. Marked satisfied, upgrade search is off."
								: "Grabbed release is below this profile. Keeping it monitored for upgrades."}
						</span>
						<button
							onClick={() =>
								overrideMonitoringMutation.mutate(
									grabMonitoringMode === "satisfied"
										? "monitoring"
										: "satisfied",
								)
							}
							disabled={overrideMonitoringMutation.isPending}
							className="shrink-0 rounded-md border border-border px-3 py-1 text-foreground hover:bg-muted disabled:opacity-50 cursor-pointer transition"
						>
							{grabMonitoringMode === "satisfied"
								? "Keep monitoring for upgrades"
								: "Mark satisfied"}
						</button>
					</div>
				)}

				<div className="flex-1 overflow-y-auto p-4">
					{isLoading || isFetching ? (
						<div className="flex flex-col items-center justify-center py-16">
							<Loader2 className="w-10 h-10 animate-spin text-primary mb-4" />
							<p className="text-muted-foreground">
								Searching indexers...
							</p>
						</div>
					) : displayResults.length > 0 ? (
						<div className="space-y-2">
							<div className="text-sm text-muted-foreground mb-3">
								{manualRelease ? (
									<span>Pasted link ready to grab</span>
								) : (
									<>
										{processedResults.length} results found
										{searchResults &&
											processedResults.length !==
												searchResults.length && (
												<span>
													{" "}
													(
													{searchResults.length -
														processedResults.length}{" "}
													filtered)
												</span>
											)}
									</>
								)}
							</div>
							{displayResults.map((result, index) => (
								<div
									key={index}
									className="bg-muted/50 rounded-lg p-4 border border-border hover:border-primary/50 transition"
								>
									<div className="flex items-start justify-between gap-4">
										<div className="flex-1 min-w-0">
											{result.indexer_page_url ||
											result.torrent_url ? (
												<a
													href={
														result.indexer_page_url ||
														result.torrent_url
													}
													target="_blank"
													rel="noopener noreferrer"
													onClick={(e) =>
														e.stopPropagation()
													}
													className="block font-medium text-sm truncate mb-2 hover:text-primary hover:underline"
													title={`Open release page: ${result.title}`}
												>
													{result.title}
												</a>
											) : (
												<h4
													className="font-medium text-sm truncate mb-2"
													title={result.title}
												>
													{result.title}
												</h4>
											)}
											<div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
												<span className="flex items-center gap-1">
													<HardDrive className="w-3.5 h-3.5" />
													{formatSize(result.size)}
												</span>
												<span className="flex items-center gap-1 text-green-500">
													<Users className="w-3.5 h-3.5" />
													{result.seeders} seeders
												</span>
												{result.quality && (
													<span className="px-2 py-0.5 bg-primary/20 text-primary rounded">
														{result.quality}
													</span>
												)}
												{result.source && (
													<span className="px-2 py-0.5 bg-muted rounded">
														{result.source}
													</span>
												)}
												<span className="flex items-center gap-1">
													<Clock className="w-3.5 h-3.5" />
													{result.indexer}
												</span>
												{result.uploader && (
													<span className="flex items-center gap-1">
														<User className="w-3.5 h-3.5" />
														{result.uploader}
													</span>
												)}
											</div>
										</div>
										<div className="flex items-center gap-2">
											<button
												onClick={() =>
													startGrab(result)
												}
												disabled={
													downloadMutation.isPending
												}
												className="p-2 bg-green-600 text-white rounded-lg hover:opacity-90 transition cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
												title="Download"
											>
												{downloadMutation.isPending ? (
													<Loader2 className="w-4 h-4 animate-spin" />
												) : (
													<Download className="w-4 h-4" />
												)}
											</button>
										</div>
									</div>
								</div>
							))}
						</div>
					) : searchResults ? (
						<div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
							<Search className="w-12 h-12 mb-4 opacity-50" />
							<p>No results found</p>
							<p className="text-sm">
								Try a different search term or adjust filters
							</p>
						</div>
					) : (
						<div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
							<Search className="w-12 h-12 mb-4 opacity-50" />
							<p>Click Search to find releases</p>
						</div>
					)}
				</div>

				<div className="p-4 border-t border-border flex justify-end">
					<button
						onClick={onClose}
						className="px-6 py-2 bg-muted text-foreground rounded-lg hover:opacity-90 transition cursor-pointer"
					>
						Close
					</button>
				</div>
			</div>

			{/* Pre-grab confirmation: choose satisfied vs keep-monitoring before downloading. */}
			{pendingGrab && (
				<div
					className="fixed inset-0 z-[80] flex items-center justify-center bg-black/60 p-4"
					onClick={() => setPendingGrab(null)}
				>
					<div
						className="w-full max-w-md rounded-lg border border-border bg-card p-5 shadow-xl"
						onClick={(e) => e.stopPropagation()}
					>
						<h3 className="text-base font-semibold mb-1">
							Download release
						</h3>
						<p
							className="text-sm text-muted-foreground truncate mb-4"
							title={pendingGrab.title}
						>
							{pendingGrab.title}
						</p>
						<div className="space-y-2 mb-5">
							<label className="flex items-start gap-3 rounded-lg border border-border p-3 cursor-pointer hover:bg-muted/50">
								<input
									type="radio"
									name="grab-monitoring"
									checked={pendingChoice === "monitoring"}
									onChange={() =>
										setPendingChoice("monitoring")
									}
									className="mt-1 cursor-pointer"
								/>
								<span>
									<span className="block text-sm font-medium">
										Keep monitoring for upgrades
									</span>
									<span className="block text-xs text-muted-foreground">
										Download this now and keep searching for
										a better release later.
									</span>
								</span>
							</label>
							<label className="flex items-start gap-3 rounded-lg border border-border p-3 cursor-pointer hover:bg-muted/50">
								<input
									type="radio"
									name="grab-monitoring"
									checked={pendingChoice === "satisfied"}
									onChange={() =>
										setPendingChoice("satisfied")
									}
									className="mt-1 cursor-pointer"
								/>
								<span>
									<span className="block text-sm font-medium">
										Mark satisfied
									</span>
									<span className="block text-xs text-muted-foreground">
										Treat this as fulfilling the profile and
										stop upgrade searches.
									</span>
								</span>
							</label>
						</div>
						<div className="flex justify-end gap-2">
							<button
								onClick={() => setPendingGrab(null)}
								className="px-4 py-2 rounded-lg bg-muted text-foreground hover:opacity-90 transition cursor-pointer"
							>
								Cancel
							</button>
							<button
								onClick={() => {
									const result = pendingGrab;
									const keepMonitoring =
										pendingChoice === "monitoring";
									setPendingGrab(null);
									downloadMutation.mutate({
										result,
										keepMonitoring,
									});
								}}
								disabled={downloadMutation.isPending}
								className="px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:opacity-90 transition cursor-pointer disabled:opacity-50 flex items-center gap-2"
							>
								{downloadMutation.isPending ? (
									<Loader2 className="w-4 h-4 animate-spin" />
								) : (
									<Download className="w-4 h-4" />
								)}
								Download
							</button>
						</div>
					</div>
				</div>
			)}

			{toast && (
				<Toast
					message={toast.message}
					type={toast.type}
					onClose={() => setToast(null)}
				/>
			)}
		</div>
	);
}
