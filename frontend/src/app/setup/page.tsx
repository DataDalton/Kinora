"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { testFolderPaths } from "@/lib/api/root-folders";
import { useRouter } from "next/navigation";
import {
	Check,
	ChevronRight,
	Server,
	Key,
	Folder,
	Loader2,
	FolderOpen,
	Plus,
	Trash2,
	ChevronDown,
	ChevronUp,
	Link,
	AlertTriangle,
	X,
	ArrowUp,
	ArrowDown,
} from "lucide-react";

interface SetupStatus {
	isSetupComplete: boolean;
	hasDownloadClient: boolean;
	hasTmdbKey: boolean;
	hasRootFolders: boolean;
	isAdmin: boolean;
}

type SetupStep = "qbittorrent" | "tmdb" | "folders" | "complete";

type MediaType = "movies" | "shows" | "anime" | "music";

interface FolderTestStatus {
	testing: boolean;
	success: boolean | null;
	hardlinkSupported: boolean | null;
	message: string | null;
}

interface FolderItem {
	id: string;
	name: string;
	rootPath: string;
	downloadPath: string;
	fillThresholdPercent?: number;
	fillThresholdGb?: number;
	testStatus?: FolderTestStatus;
}

interface FoldersData {
	movies: FolderItem[];
	shows: FolderItem[];
	anime: FolderItem[];
	music: FolderItem[];
	selectionModes: Record<MediaType, string>;
}

const mediaTypeLabels: Record<MediaType, string> = {
	movies: "Movies",
	shows: "TV Shows",
	anime: "Anime",
	music: "Music",
};

const generateId = () => Math.random().toString(36).substring(2, 11);

const generateDownloadPath = (rootPath: string, mediaType: string): string => {
	if (!rootPath) return "";
	const isWindows = rootPath.includes("\\") || /^[A-Z]:/.test(rootPath);
	const separator = isWindows ? "\\" : "/";
	const parentPath = rootPath.split(separator).slice(0, -1).join(separator);
	return `${parentPath}${separator}downloads${separator}${mediaType}`;
};

export default function SetupPage() {
	const router = useRouter();
	const queryClient = useQueryClient();
	const [currentStep, setCurrentStep] = useState<SetupStep>("qbittorrent");
	const [isRedirecting, setIsRedirecting] = useState(false);
	const [expandedTypes, setExpandedTypes] = useState<
		Record<MediaType, boolean>
	>({
		movies: false,
		shows: false,
		anime: false,
		music: false,
	});

	const [qbittorrentData, setQBittorrentData] = useState({
		name: "qBittorrent",
		host: "localhost",
		port: 8080,
		username: "admin",
		password: "",
		use_ssl: false,
	});

	const [tmdbData, setTmdbData] = useState({
		api_key: "",
	});

	const [foldersData, setFoldersData] = useState<FoldersData>({
		movies: [
			{
				id: generateId(),
				name: "Movies",
				rootPath: "",
				downloadPath: "",
			},
		],
		shows: [
			{
				id: generateId(),
				name: "TV Shows",
				rootPath: "",
				downloadPath: "",
			},
		],
		anime: [
			{ id: generateId(), name: "Anime", rootPath: "", downloadPath: "" },
		],
		music: [
			{ id: generateId(), name: "Music", rootPath: "", downloadPath: "" },
		],
		selectionModes: {
			movies: "most_free_space",
			shows: "most_free_space",
			anime: "most_free_space",
			music: "most_free_space",
		},
	});

	const [showBrowser, setShowBrowser] = useState(false);
	const [browserTarget, setBrowserTarget] = useState<{
		mediaType: MediaType;
		folderId: string;
		field: "rootPath" | "downloadPath";
	} | null>(null);
	const [currentBrowserPath, setCurrentBrowserPath] = useState("/");
	const [manualPath, setManualPath] = useState("/");
	const [isWindows] = useState(
		() =>
			typeof navigator !== "undefined" &&
			navigator.platform.toLowerCase().includes("win"),
	);

	// Track pending tests to debounce API calls
	const testTimeouts = useRef<Record<string, NodeJS.Timeout>>({});

	// Test folder paths and update status
	const testFolderConfig = useCallback(
		async (
			mediaType: MediaType,
			folderId: string,
			rootPath: string,
			downloadPath: string,
		) => {
			// Skip if either path is empty
			if (!rootPath || !downloadPath) {
				setFoldersData((prev) => ({
					...prev,
					[mediaType]: prev[mediaType].map((f) =>
						f.id === folderId ? { ...f, testStatus: undefined } : f,
					),
				}));
				return;
			}

			// Set testing state
			setFoldersData((prev) => ({
				...prev,
				[mediaType]: prev[mediaType].map((f) =>
					f.id === folderId
						? {
								...f,
								testStatus: {
									testing: true,
									success: null,
									hardlinkSupported: null,
									message: null,
								},
							}
						: f,
				),
			}));

			try {
				const result = await testFolderPaths(rootPath, downloadPath);
				setFoldersData((prev) => ({
					...prev,
					[mediaType]: prev[mediaType].map((f) =>
						f.id === folderId
							? {
									...f,
									testStatus: {
										testing: false,
										success: result.success,
										hardlinkSupported:
											result.hardlinkSupported,
										message: result.message,
									},
								}
							: f,
					),
				}));
			} catch {
				setFoldersData((prev) => ({
					...prev,
					[mediaType]: prev[mediaType].map((f) =>
						f.id === folderId
							? {
									...f,
									testStatus: {
										testing: false,
										success: false,
										hardlinkSupported: false,
										message:
											"Failed to test folder configuration",
									},
								}
							: f,
					),
				}));
			}
		},
		[],
	);

	// Debounced test trigger when paths change
	const triggerFolderTest = useCallback(
		(
			mediaType: MediaType,
			folderId: string,
			rootPath: string,
			downloadPath: string,
		) => {
			const key = `${mediaType}-${folderId}`;

			// Clear existing timeout for this folder
			if (testTimeouts.current[key]) {
				clearTimeout(testTimeouts.current[key]);
			}

			// Set new timeout to debounce rapid changes
			testTimeouts.current[key] = setTimeout(() => {
				testFolderConfig(mediaType, folderId, rootPath, downloadPath);
			}, 500);
		},
		[testFolderConfig],
	);

	// Fetch setup status
	const { data: setupStatus, isLoading: statusLoading } =
		useQuery<SetupStatus>({
			queryKey: ["setup-status"],
			queryFn: async () => {
				const response = await api.get("/setup/status");
				const data = response.data;
				return {
					isSetupComplete: data.is_setup_complete,
					hasDownloadClient: data.has_download_client,
					hasTmdbKey: data.has_tmdb_key,
					hasRootFolders: data.has_root_folders,
					isAdmin: data.is_admin,
				};
			},
		});

	// Fetch directory contents for browser
	const {
		data: browserData,
		isLoading: browserLoading,
		error: browserError,
		refetch: refetchBrowser,
	} = useQuery({
		queryKey: ["browse-directory", currentBrowserPath],
		queryFn: async () => {
			const response = await api.get(
				`/setup/browse-directory?path=${encodeURIComponent(currentBrowserPath)}`,
			);
			return response.data;
		},
		enabled: showBrowser,
		retry: 1,
	});

	// Sync manual path input with actual browser path
	useEffect(() => {
		if (browserData?.current_path) {
			setManualPath(browserData.current_path);
		}
	}, [browserData]);

	// Redirect if not admin
	useEffect(() => {
		if (setupStatus && !setupStatus.isAdmin) {
			setIsRedirecting(true);
			router.push("/");
		}
	}, [setupStatus, router]);

	// Redirect if setup is already complete
	useEffect(() => {
		if (setupStatus?.isSetupComplete && currentStep !== "complete") {
			setIsRedirecting(true);
			router.push("/");
		}
	}, [setupStatus?.isSetupComplete, currentStep, router]);

	// Configure qBittorrent
	const qbittorrentMutation = useMutation({
		mutationFn: async () => {
			const response = await api.post(
				"/setup/qbittorrent",
				qbittorrentData,
			);
			return response.data;
		},
		onSuccess: async () => {
			await queryClient.invalidateQueries({ queryKey: ["setup-status"] });
			setCurrentStep("tmdb");
		},
	});

	// Configure TMDB
	const tmdbMutation = useMutation({
		mutationFn: async () => {
			const response = await api.post("/setup/tmdb", tmdbData);
			return response.data;
		},
		onSuccess: async () => {
			await queryClient.invalidateQueries({ queryKey: ["setup-status"] });
			setCurrentStep("folders");
		},
	});

	// Configure folders - transform to backend format
	const foldersMutation = useMutation({
		mutationFn: async () => {
			const transformFolder = (f: FolderItem) => ({
				name: f.name,
				root_path: f.rootPath,
				download_path: f.downloadPath || undefined,
				fill_threshold_percent: f.fillThresholdPercent,
				fill_threshold_gb: f.fillThresholdGb,
			});
			const payload = {
				movies: foldersData.movies.map(transformFolder),
				shows: foldersData.shows.map(transformFolder),
				anime: foldersData.anime.map(transformFolder),
				music: foldersData.music.map(transformFolder),
				selection_modes: foldersData.selectionModes,
			};
			const response = await api.post("/setup/root-folders", payload);
			return response.data;
		},
		onSuccess: async () => {
			await queryClient.invalidateQueries({ queryKey: ["setup-status"] });
			setCurrentStep("complete");
		},
	});

	// Complete setup
	const completeMutation = useMutation({
		mutationFn: async () => {
			const response = await api.post("/setup/complete");
			return response.data;
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["setup-status"] });
			router.push("/");
		},
	});

	const openBrowser = (
		mediaType: MediaType,
		folderId: string,
		field: "rootPath" | "downloadPath",
	) => {
		setBrowserTarget({ mediaType, folderId, field });
		setCurrentBrowserPath("/");
		setManualPath("/");
		setShowBrowser(true);
	};

	const navigateToManualPath = () => {
		setCurrentBrowserPath(manualPath);
	};

	const selectFolder = (path: string) => {
		if (browserTarget) {
			const { mediaType, folderId, field } = browserTarget;
			setFoldersData((prev) => {
				const newData = {
					...prev,
					[mediaType]: prev[mediaType].map((f) => {
						if (f.id === folderId) {
							const updated = { ...f, [field]: path };
							// Auto-generate download path when root path is set
							if (field === "rootPath" && !f.downloadPath) {
								updated.downloadPath = generateDownloadPath(
									path,
									mediaType,
								);
							}
							return updated;
						}
						return f;
					}),
				};

				// Trigger test after path selection
				const folder = newData[mediaType].find(
					(f) => f.id === folderId,
				);
				if (folder) {
					triggerFolderTest(
						mediaType,
						folderId,
						folder.rootPath,
						folder.downloadPath,
					);
				}

				return newData;
			});
			setShowBrowser(false);
			setBrowserTarget(null);
		}
	};

	const addFolder = (mediaType: MediaType) => {
		const newFolder: FolderItem = {
			id: generateId(),
			name: `${mediaTypeLabels[mediaType]} ${foldersData[mediaType].length + 1}`,
			rootPath: "",
			downloadPath: "",
		};
		setFoldersData((prev) => ({
			...prev,
			[mediaType]: [...prev[mediaType], newFolder],
		}));
	};

	const removeFolder = (mediaType: MediaType, folderId: string) => {
		const folders = foldersData[mediaType];
		if (folders.length <= 1) return;

		const updatedFolders = folders.filter((f) => f.id !== folderId);

		setFoldersData((prev) => ({
			...prev,
			[mediaType]: updatedFolders,
		}));
	};

	const updateFolder = (
		mediaType: MediaType,
		folderId: string,
		field: keyof FolderItem,
		value: string | boolean | number | undefined,
	) => {
		setFoldersData((prev) => {
			const newData = {
				...prev,
				[mediaType]: prev[mediaType].map((f) => {
					if (f.id === folderId) {
						const updated = { ...f, [field]: value };
						// Auto-generate download path when root path is changed
						if (field === "rootPath" && typeof value === "string") {
							updated.downloadPath = generateDownloadPath(
								value,
								mediaType,
							);
						}
						return updated;
					}
					return f;
				}),
			};

			// Trigger test if path fields changed
			if (field === "rootPath" || field === "downloadPath") {
				const folder = newData[mediaType].find(
					(f) => f.id === folderId,
				);
				if (folder) {
					triggerFolderTest(
						mediaType,
						folderId,
						folder.rootPath,
						folder.downloadPath,
					);
				}
			}

			return newData;
		});
	};

	const toggleExpanded = (mediaType: MediaType) => {
		setExpandedTypes((prev) => ({
			...prev,
			[mediaType]: !prev[mediaType],
		}));
	};

	const moveFolder = (
		mediaType: MediaType,
		folderId: string,
		direction: "up" | "down",
	) => {
		setFoldersData((prev) => {
			const folders = [...prev[mediaType]];
			const currentIndex = folders.findIndex((f) => f.id === folderId);
			if (currentIndex === -1) return prev;

			const swapIndex =
				direction === "up" ? currentIndex - 1 : currentIndex + 1;
			if (swapIndex < 0 || swapIndex >= folders.length) return prev;

			// Swap folders
			[folders[currentIndex], folders[swapIndex]] = [
				folders[swapIndex],
				folders[currentIndex],
			];

			return {
				...prev,
				[mediaType]: folders,
			};
		});
	};

	const isFoldersValid = () => {
		const mediaTypes: MediaType[] = ["movies", "shows", "anime", "music"];
		return mediaTypes.every(
			(type) =>
				foldersData[type].length > 0 &&
				foldersData[type].every((f) => f.name && f.rootPath),
		);
	};

	const steps = [
		{
			id: "qbittorrent",
			name: "Download Client",
			icon: Server,
			completed: setupStatus?.hasDownloadClient,
		},
		{
			id: "tmdb",
			name: "TMDB API",
			icon: Key,
			completed: setupStatus?.hasTmdbKey,
		},
		{
			id: "folders",
			name: "Root Folders",
			icon: Folder,
			completed: setupStatus?.hasRootFolders,
		},
	];

	if (statusLoading || isRedirecting) {
		return (
			<div className="min-h-screen flex items-center justify-center">
				<Loader2 className="w-8 h-8 animate-spin text-primary" />
			</div>
		);
	}

	return (
		<div className="min-h-screen bg-background">
			<div className="flex">
				{/* Left Navigation */}
				<div className="w-64 bg-card border-r border-border p-6 min-h-screen">
					<h2 className="text-xl font-bold mb-6">Initial Setup</h2>
					<nav className="space-y-2">
						{steps.map((step) => {
							const StepIcon = step.icon;
							const isActive = currentStep === step.id;
							const isCompleted = step.completed;

							return (
								<button
									key={step.id}
									onClick={() =>
										setCurrentStep(step.id as SetupStep)
									}
									className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors cursor-pointer ${
										isActive
											? "bg-primary text-primary-foreground"
											: isCompleted
												? "bg-green-500/10 text-green-500"
												: "hover:bg-accent"
									}`}
								>
									<div className="flex-shrink-0">
										{isCompleted ? (
											<Check className="w-5 h-5" />
										) : (
											<StepIcon className="w-5 h-5" />
										)}
									</div>
									<span className="flex-1 text-left text-sm font-medium">
										{step.name}
									</span>
									{isActive && (
										<ChevronRight className="w-4 h-4" />
									)}
								</button>
							);
						})}
					</nav>
				</div>

				{/* Main Content */}
				<div className="flex-1 p-8">
					<div className="max-w-3xl mx-auto">
						{/* qBittorrent Setup */}
						{currentStep === "qbittorrent" && (
							<div>
								<h1 className="text-3xl font-bold mb-2">
									Configure Download Client
								</h1>
								<p className="text-muted-foreground mb-6">
									Connect to qBittorrent to download media
									files
								</p>

								<div className="space-y-4">
									<div>
										<label className="block text-sm font-medium mb-2">
											Display Name
										</label>
										<input
											type="text"
											value={qbittorrentData.name}
											onChange={(e) =>
												setQBittorrentData({
													...qbittorrentData,
													name: e.target.value,
												})
											}
											className="w-full px-4 py-2 bg-card border border-border rounded-lg focus:outline-none focus:border-primary"
										/>
									</div>

									<div className="grid grid-cols-2 gap-4">
										<div>
											<label className="block text-sm font-medium mb-2">
												Host
											</label>
											<input
												type="text"
												value={qbittorrentData.host}
												onChange={(e) =>
													setQBittorrentData({
														...qbittorrentData,
														host: e.target.value,
													})
												}
												placeholder="localhost"
												className="w-full px-4 py-2 bg-card border border-border rounded-lg focus:outline-none focus:border-primary"
											/>
										</div>

										<div>
											<label className="block text-sm font-medium mb-2">
												Port
											</label>
											<input
												type="number"
												value={qbittorrentData.port}
												onChange={(e) =>
													setQBittorrentData({
														...qbittorrentData,
														port: parseInt(
															e.target.value,
														),
													})
												}
												className="w-full px-4 py-2 bg-card border border-border rounded-lg focus:outline-none focus:border-primary"
											/>
										</div>
									</div>

									<div className="grid grid-cols-2 gap-4">
										<div>
											<label className="block text-sm font-medium mb-2">
												Username
											</label>
											<input
												type="text"
												value={qbittorrentData.username}
												onChange={(e) =>
													setQBittorrentData({
														...qbittorrentData,
														username:
															e.target.value,
													})
												}
												className="w-full px-4 py-2 bg-card border border-border rounded-lg focus:outline-none focus:border-primary"
											/>
										</div>

										<div>
											<label className="block text-sm font-medium mb-2">
												Password
											</label>
											<input
												type="password"
												value={qbittorrentData.password}
												onChange={(e) =>
													setQBittorrentData({
														...qbittorrentData,
														password:
															e.target.value,
													})
												}
												className="w-full px-4 py-2 bg-card border border-border rounded-lg focus:outline-none focus:border-primary"
											/>
										</div>
									</div>

									<div className="flex items-center justify-between">
										<label
											htmlFor="use_ssl"
											className="text-sm font-medium"
										>
											Use SSL (HTTPS)
										</label>
										<button
											type="button"
											id="use_ssl"
											onClick={() =>
												setQBittorrentData({
													...qbittorrentData,
													use_ssl:
														!qbittorrentData.use_ssl,
												})
											}
											className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors cursor-pointer ${
												qbittorrentData.use_ssl
													? "bg-primary"
													: "bg-muted"
											}`}
										>
											<span
												className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
													qbittorrentData.use_ssl
														? "translate-x-6"
														: "translate-x-1"
												}`}
											/>
										</button>
									</div>

									{qbittorrentMutation.isError && (
										<div className="p-4 bg-red-500/10 border border-red-500/50 rounded-lg text-red-500 text-sm">
											{(qbittorrentMutation.error as any)
												?.response?.data?.detail ||
												"Failed to connect to qBittorrent"}
										</div>
									)}

									<button
										onClick={() =>
											qbittorrentMutation.mutate()
										}
										disabled={
											qbittorrentMutation.isPending ||
											!qbittorrentData.password
										}
										className="w-full px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed font-medium flex items-center justify-center gap-2"
									>
										{qbittorrentMutation.isPending ? (
											<>
												<Loader2 className="w-5 h-5 animate-spin" />
												Testing Connection...
											</>
										) : (
											"Test & Continue"
										)}
									</button>
								</div>
							</div>
						)}

						{/* TMDB Setup */}
						{currentStep === "tmdb" && (
							<div>
								<h1 className="text-3xl font-bold mb-2">
									Configure TMDB API
								</h1>
								<p className="text-muted-foreground mb-6">
									TMDB API key is required to fetch movie and
									TV show metadata
								</p>

								<div className="space-y-4">
									<div>
										<label className="block text-sm font-medium mb-2">
											TMDB API Key (v3)
										</label>
										<input
											type="text"
											value={tmdbData.api_key}
											onChange={(e) =>
												setTmdbData({
													api_key: e.target.value,
												})
											}
											placeholder="Enter your TMDB API key"
											className="w-full px-4 py-2 bg-card border border-border rounded-lg focus:outline-none focus:border-primary font-mono text-sm"
										/>
										<p className="text-xs text-muted-foreground mt-2">
											Don't have an API key?{" "}
											<a
												href="https://www.themoviedb.org/settings/api"
												target="_blank"
												rel="noopener noreferrer"
												className="text-primary hover:underline"
											>
												Get one from TMDB
											</a>
										</p>
									</div>

									{tmdbMutation.isError && (
										<div className="p-4 bg-red-500/10 border border-red-500/50 rounded-lg text-red-500 text-sm">
											{(tmdbMutation.error as any)
												?.response?.data?.detail ||
												"Invalid TMDB API key"}
										</div>
									)}

									<div className="flex gap-3">
										<button
											onClick={() =>
												setCurrentStep("qbittorrent")
											}
											className="px-6 py-3 bg-card border border-border rounded-lg hover:bg-accent font-medium cursor-pointer"
										>
											Back
										</button>
										<button
											onClick={() =>
												tmdbMutation.mutate()
											}
											disabled={
												tmdbMutation.isPending ||
												tmdbData.api_key.length < 32
											}
											className="flex-1 px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed font-medium flex items-center justify-center gap-2"
										>
											{tmdbMutation.isPending ? (
												<>
													<Loader2 className="w-5 h-5 animate-spin" />
													Validating...
												</>
											) : (
												"Validate & Continue"
											)}
										</button>
									</div>
								</div>
							</div>
						)}

						{/* Folders Setup */}
						{currentStep === "folders" && (
							<div>
								<h1 className="text-3xl font-bold mb-2">
									Configure Root Folders
								</h1>
								<p className="text-muted-foreground mb-6">
									Set where your media files will be
									organized. Each root folder is paired with a
									download folder on the same filesystem to
									enable hardlinking.
								</p>

								<div className="space-y-4">
									{/* Media Type Sections */}
									{(
										[
											"movies",
											"shows",
											"anime",
											"music",
										] as MediaType[]
									).map((mediaType) => (
										<div
											key={mediaType}
											className="border border-border rounded-lg overflow-hidden"
										>
											<button
												onClick={() =>
													toggleExpanded(mediaType)
												}
												className="w-full flex items-center justify-between p-4 bg-card hover:bg-accent transition cursor-pointer"
											>
												<div className="flex items-center gap-3">
													<Folder className="w-5 h-5 text-primary" />
													<span className="font-medium">
														{
															mediaTypeLabels[
																mediaType
															]
														}
													</span>
													<span className="text-sm text-muted-foreground">
														(
														{
															foldersData[
																mediaType
															].length
														}{" "}
														folder
														{foldersData[mediaType]
															.length !== 1
															? "s"
															: ""}
														)
													</span>
												</div>
												{expandedTypes[mediaType] ? (
													<ChevronUp className="w-5 h-5 text-muted-foreground" />
												) : (
													<ChevronDown className="w-5 h-5 text-muted-foreground" />
												)}
											</button>

											{expandedTypes[mediaType] && (
												<div className="p-4 space-y-4 bg-background">
													{/* Selection Mode for this media type */}
													<div className="p-3 bg-muted/30 border border-border rounded-lg">
														<label className="block text-sm font-medium mb-2">
															Folder Selection
															Mode
														</label>
														<select
															value={
																foldersData
																	.selectionModes[
																	mediaType
																]
															}
															onChange={(e) =>
																setFoldersData(
																	(prev) => ({
																		...prev,
																		selectionModes:
																			{
																				...prev.selectionModes,
																				[mediaType]:
																					e
																						.target
																						.value,
																			},
																	}),
																)
															}
															className="w-full px-3 py-2 bg-background border border-border rounded-lg focus:outline-none focus:border-primary cursor-pointer text-sm"
														>
															<option value="most_free_space">
																Most Free Space
															</option>
															<option value="priority">
																Priority Order
															</option>
															<option value="fill_threshold">
																Fill Threshold
															</option>
														</select>
														<p className="text-xs text-muted-foreground mt-1.5">
															{foldersData
																.selectionModes[
																mediaType
															] ===
																"most_free_space" &&
																"Always use the folder with most available space."}
															{foldersData
																.selectionModes[
																mediaType
															] === "priority" &&
																"Fill folders in your defined order (1→2→3)."}
															{foldersData
																.selectionModes[
																mediaType
															] ===
																"fill_threshold" &&
																"Among folders under threshold, always picks most free space."}
														</p>
													</div>

													{foldersData[mediaType].map(
														(folder, index) => (
															<div
																key={folder.id}
																className="p-4 bg-card border border-border rounded-lg space-y-3"
															>
																<div className="flex items-center justify-between">
																	<div className="flex items-center gap-2">
																		{/* Priority Reorder Controls */}
																		{foldersData
																			.selectionModes[
																			mediaType
																		] ===
																			"priority" &&
																			foldersData[
																				mediaType
																			]
																				.length >
																				1 && (
																				<div className="flex items-center gap-1 mr-2">
																					<button
																						onClick={() =>
																							moveFolder(
																								mediaType,
																								folder.id,
																								"up",
																							)
																						}
																						disabled={
																							index ===
																							0
																						}
																						className="p-1 rounded hover:bg-muted disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer transition"
																						title="Move up in priority"
																					>
																						<ArrowUp className="w-3 h-3" />
																					</button>
																					<span className="text-xs font-medium text-muted-foreground w-4 text-center">
																						{index +
																							1}
																					</span>
																					<button
																						onClick={() =>
																							moveFolder(
																								mediaType,
																								folder.id,
																								"down",
																							)
																						}
																						disabled={
																							index ===
																							foldersData[
																								mediaType
																							]
																								.length -
																								1
																						}
																						className="p-1 rounded hover:bg-muted disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer transition"
																						title="Move down in priority"
																					>
																						<ArrowDown className="w-3 h-3" />
																					</button>
																				</div>
																			)}
																		<span className="text-sm font-medium text-muted-foreground">
																			Folder{" "}
																			{index +
																				1}
																		</span>
																	</div>
																	<div className="flex items-center gap-2">
																		{foldersData[
																			mediaType
																		]
																			.length >
																			1 && (
																			<button
																				onClick={() =>
																					removeFolder(
																						mediaType,
																						folder.id,
																					)
																				}
																				className="p-1.5 text-muted-foreground hover:text-red-500 hover:bg-red-500/10 rounded transition cursor-pointer"
																				title="Remove folder"
																			>
																				<Trash2 className="w-4 h-4" />
																			</button>
																		)}
																	</div>
																</div>

																<div>
																	<label className="block text-xs font-medium mb-1 text-muted-foreground">
																		Name
																	</label>
																	<input
																		type="text"
																		value={
																			folder.name
																		}
																		onChange={(
																			e,
																		) =>
																			updateFolder(
																				mediaType,
																				folder.id,
																				"name",
																				e
																					.target
																					.value,
																			)
																		}
																		placeholder="Folder name"
																		className="w-full px-3 py-2 bg-background border border-border rounded-lg focus:outline-none focus:border-primary text-sm"
																	/>
																</div>

																<div>
																	<label className="block text-xs font-medium mb-1 text-muted-foreground">
																		Root
																		Path
																		(organized
																		media)
																	</label>
																	<div className="flex gap-2">
																		<input
																			type="text"
																			value={
																				folder.rootPath
																			}
																			onChange={(
																				e,
																			) =>
																				updateFolder(
																					mediaType,
																					folder.id,
																					"rootPath",
																					e
																						.target
																						.value,
																				)
																			}
																			placeholder={
																				isWindows
																					? `D:\\Media\\${mediaTypeLabels[mediaType]}`
																					: `/media/${mediaType}`
																			}
																			className="flex-1 px-3 py-2 bg-background border border-border rounded-lg focus:outline-none focus:border-primary font-mono text-sm"
																		/>
																		<button
																			type="button"
																			onClick={() =>
																				openBrowser(
																					mediaType,
																					folder.id,
																					"rootPath",
																				)
																			}
																			className="px-3 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition flex items-center gap-2 cursor-pointer"
																		>
																			<FolderOpen className="w-4 h-4" />
																		</button>
																	</div>
																</div>

																<div>
																	<label className="block text-xs font-medium mb-1 text-muted-foreground">
																		Download
																		Path
																		(same
																		filesystem)
																	</label>
																	<div className="flex gap-2">
																		<input
																			type="text"
																			value={
																				folder.downloadPath
																			}
																			onChange={(
																				e,
																			) =>
																				updateFolder(
																					mediaType,
																					folder.id,
																					"downloadPath",
																					e
																						.target
																						.value,
																				)
																			}
																			placeholder={
																				isWindows
																					? `D:\\Downloads\\${mediaType}`
																					: `/downloads/${mediaType}`
																			}
																			className="flex-1 px-3 py-2 bg-background border border-border rounded-lg focus:outline-none focus:border-primary font-mono text-sm"
																		/>
																		<button
																			type="button"
																			onClick={() =>
																				openBrowser(
																					mediaType,
																					folder.id,
																					"downloadPath",
																				)
																			}
																			className="px-3 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition flex items-center gap-2 cursor-pointer"
																		>
																			<FolderOpen className="w-4 h-4" />
																		</button>
																	</div>
																	<p className="text-xs text-muted-foreground mt-1">
																		Must be
																		on the
																		same
																		drive/filesystem
																		as root
																		path for
																		hardlinking
																	</p>
																</div>

																{/* Fill Threshold Settings */}
																{(foldersData
																	.selectionModes[
																	mediaType
																] ===
																	"fill_threshold" ||
																	foldersData
																		.selectionModes[
																		mediaType
																	] ===
																		"priority") && (
																	<div className="grid grid-cols-2 gap-3">
																		<div>
																			<label className="block text-xs font-medium mb-1 text-muted-foreground">
																				Max
																				Disk
																				Usage
																				<span className="ml-2 text-primary font-semibold">
																					{folder.fillThresholdPercent ??
																						"Off"}
																					{folder.fillThresholdPercent
																						? "%"
																						: ""}
																				</span>
																			</label>
																			<input
																				type="range"
																				min={
																					0
																				}
																				max={
																					100
																				}
																				step={
																					5
																				}
																				value={
																					folder.fillThresholdPercent ??
																					0
																				}
																				onChange={(
																					e,
																				) =>
																					updateFolder(
																						mediaType,
																						folder.id,
																						"fillThresholdPercent",
																						parseInt(
																							e
																								.target
																								.value,
																						) ||
																							undefined,
																					)
																				}
																				className="w-full h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
																			/>
																			<div className="grid grid-cols-3 text-xs text-muted-foreground mt-1">
																				<span>
																					Off
																				</span>
																				<span className="text-center">
																					50%
																				</span>
																				<span className="text-right">
																					100%
																				</span>
																			</div>
																		</div>
																		<div>
																			<label className="block text-xs font-medium mb-1 text-muted-foreground">
																				Min
																				Free
																				Space
																			</label>
																			<input
																				type="number"
																				min={
																					0
																				}
																				value={
																					folder.fillThresholdGb ??
																					""
																				}
																				onChange={(
																					e,
																				) =>
																					updateFolder(
																						mediaType,
																						folder.id,
																						"fillThresholdGb",
																						e
																							.target
																							.value
																							? parseInt(
																									e
																										.target
																										.value,
																								)
																							: undefined,
																					)
																				}
																				placeholder="GB"
																				className="w-full px-3 py-2 bg-background border border-border rounded-lg focus:outline-none focus:border-primary text-sm [&::-webkit-inner-spin-button]:dark:invert [&::-webkit-outer-spin-button]:dark:invert"
																			/>
																		</div>
																		<p className="col-span-2 text-xs text-muted-foreground">
																			Move
																			to
																			next
																			folder
																			when
																			disk
																			usage
																			reaches
																			threshold
																		</p>
																	</div>
																)}

																{/* Hardlink Status Banner */}
																{folder.testStatus && (
																	<div
																		className={`flex items-center gap-2 p-3 rounded-lg text-sm ${
																			folder
																				.testStatus
																				.testing
																				? "bg-muted/50 text-muted-foreground"
																				: folder
																							.testStatus
																							.success &&
																					  folder
																							.testStatus
																							.hardlinkSupported
																					? "bg-green-500/10 text-green-500 border border-green-500/20"
																					: folder
																								.testStatus
																								.success &&
																						  !folder
																								.testStatus
																								.hardlinkSupported
																						? "bg-yellow-500/10 text-yellow-500 border border-yellow-500/20"
																						: "bg-red-500/10 text-red-500 border border-red-500/20"
																		}`}
																	>
																		{folder
																			.testStatus
																			.testing ? (
																			<>
																				<Loader2 className="w-4 h-4 animate-spin shrink-0" />
																				<span>
																					Testing
																					folder
																					configuration...
																				</span>
																			</>
																		) : folder
																				.testStatus
																				.success &&
																		  folder
																				.testStatus
																				.hardlinkSupported ? (
																			<>
																				<Link className="w-4 h-4 shrink-0" />
																				<span>
																					Hardlinks
																					supported
																					-
																					paths
																					are
																					on
																					the
																					same
																					filesystem
																				</span>
																			</>
																		) : folder
																				.testStatus
																				.success &&
																		  !folder
																				.testStatus
																				.hardlinkSupported ? (
																			<>
																				<AlertTriangle className="w-4 h-4 shrink-0" />
																				<span>
																					Hardlinks
																					not
																					supported
																					-
																					files
																					will
																					need
																					to
																					be
																					copied
																				</span>
																			</>
																		) : (
																			<>
																				<X className="w-4 h-4 shrink-0" />
																				<span>
																					{folder
																						.testStatus
																						.message ||
																						"Folder configuration error"}
																				</span>
																			</>
																		)}
																	</div>
																)}
															</div>
														),
													)}

													<button
														onClick={() =>
															addFolder(mediaType)
														}
														className="w-full flex items-center justify-center gap-2 px-4 py-3 border border-dashed border-border rounded-lg hover:border-primary hover:text-primary transition cursor-pointer"
													>
														<Plus className="w-4 h-4" />
														Add Another Folder
													</button>
												</div>
											)}
										</div>
									))}

									{foldersMutation.isError && (
										<div className="p-4 bg-red-500/10 border border-red-500/50 rounded-lg text-red-500 text-sm">
											{(foldersMutation.error as any)
												?.response?.data?.detail ||
												"Failed to configure folders"}
										</div>
									)}

									<div className="flex gap-3">
										<button
											onClick={() =>
												setCurrentStep("tmdb")
											}
											className="px-6 py-3 bg-card border border-border rounded-lg hover:bg-accent font-medium cursor-pointer"
										>
											Back
										</button>
										<button
											onClick={() =>
												foldersMutation.mutate()
											}
											disabled={
												foldersMutation.isPending ||
												!isFoldersValid()
											}
											className="flex-1 px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed font-medium flex items-center justify-center gap-2"
										>
											{foldersMutation.isPending ? (
												<>
													<Loader2 className="w-5 h-5 animate-spin" />
													Configuring...
												</>
											) : (
												"Configure & Continue"
											)}
										</button>
									</div>
								</div>
							</div>
						)}

						{/* Complete */}
						{currentStep === "complete" && (
							<div className="text-center py-12">
								<div className="w-20 h-20 bg-green-500/10 rounded-full flex items-center justify-center mx-auto mb-6">
									<Check className="w-10 h-10 text-green-500" />
								</div>
								<h1 className="text-3xl font-bold mb-2">
									Setup Complete!
								</h1>
								<p className="text-muted-foreground mb-8">
									Your Kinora instance is now configured and
									ready to use
								</p>

								<button
									onClick={() => completeMutation.mutate()}
									disabled={completeMutation.isPending}
									className="px-8 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 font-medium flex items-center justify-center gap-2 mx-auto cursor-pointer"
								>
									{completeMutation.isPending ? (
										<>
											<Loader2 className="w-5 h-5 animate-spin" />
											Finalizing...
										</>
									) : (
										"Go to Kinora"
									)}
								</button>
							</div>
						)}
					</div>
				</div>
			</div>

			{/* File Browser Modal */}
			{showBrowser && (
				<div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
					<div className="bg-background border border-border rounded-lg w-full max-w-2xl max-h-[80vh] flex flex-col">
						<div className="p-4 border-b border-border flex items-center justify-between">
							<h3 className="text-lg font-semibold">
								Select Folder
							</h3>
							<button
								onClick={() => setShowBrowser(false)}
								className="p-2 hover:bg-accent rounded-lg transition cursor-pointer"
							>
								✕
							</button>
						</div>

						<div className="p-4 border-b border-border">
							<div className="flex items-center gap-2">
								<input
									type="text"
									value={manualPath}
									onChange={(e) =>
										setManualPath(e.target.value)
									}
									onKeyDown={(e) =>
										e.key === "Enter" &&
										navigateToManualPath()
									}
									placeholder="Enter path..."
									className="flex-1 px-3 py-2 bg-card border border-border rounded-lg font-mono text-sm focus:outline-none focus:border-primary"
								/>
								<button
									onClick={navigateToManualPath}
									className="px-4 py-2 bg-accent text-foreground rounded-lg hover:bg-accent/80 transition whitespace-nowrap cursor-pointer"
								>
									Go
								</button>
								<button
									onClick={() =>
										selectFolder(
											browserData?.current_path ||
												currentBrowserPath,
										)
									}
									className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition whitespace-nowrap cursor-pointer"
								>
									Select Current
								</button>
							</div>
						</div>

						<div className="flex-1 overflow-y-auto p-4">
							{browserLoading ? (
								<div className="flex items-center justify-center py-8">
									<Loader2 className="w-6 h-6 animate-spin text-primary" />
								</div>
							) : browserError ? (
								<div className="flex flex-col items-center justify-center py-8 gap-4">
									<div className="text-red-500 text-sm text-center">
										{(browserError as any)?.response?.data
											?.detail ||
											"Failed to browse directory"}
									</div>
									<button
										onClick={() => refetchBrowser()}
										className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition text-sm cursor-pointer"
									>
										Retry
									</button>
								</div>
							) : (
								<div className="space-y-1">
									{/* Parent directory link */}
									{browserData?.parent_path !== null &&
										browserData?.parent_path !==
											undefined && (
											<button
												onClick={() =>
													setCurrentBrowserPath(
														browserData.parent_path,
													)
												}
												className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-accent transition text-left border-b border-border cursor-pointer"
											>
												<Folder className="w-5 h-5 text-muted-foreground shrink-0" />
												<span className="font-mono text-muted-foreground">
													..
												</span>
											</button>
										)}

									{/* Directory listing */}
									{browserData?.items
										?.filter(
											(item: any) => item.is_directory,
										)
										.map((item: any) => (
											<button
												key={item.path}
												onClick={() =>
													setCurrentBrowserPath(
														item.path,
													)
												}
												className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-accent transition text-left cursor-pointer"
											>
												<Folder className="w-5 h-5 text-primary shrink-0" />
												<span className="truncate">
													{item.name}
												</span>
											</button>
										))}

									{/* Empty directory message */}
									{browserData?.items?.filter(
										(item: any) => item.is_directory,
									).length === 0 &&
										browserData?.parent_path === null && (
											<div className="text-center py-8 text-muted-foreground text-sm">
												No subdirectories found
											</div>
										)}
								</div>
							)}
						</div>
					</div>
				</div>
			)}
		</div>
	);
}
