"use client";

import { useState, useRef, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import PageHeader from "@/components/PageHeader";
import DeleteConfirmModal from "@/components/DeleteConfirmModal";
import InteractiveSearchModal from "@/components/InteractiveSearchModal";
import ManualImportModal from "@/components/ManualImportModal";
import MonitoringOptionsDropdown from "@/components/MonitoringOptionsDropdown";
import DownloadHistoryPanel from "@/components/DownloadHistoryPanel";
import FileQualityInfo from "@/components/FileQualityInfo";
import TagsEditor from "@/components/TagsEditor";
import {
	Play,
	Pause,
	Download,
	Music2,
	Clock,
	Disc3,
	ArrowLeft,
	Eye,
	EyeOff,
	Trash2,
	RefreshCw,
	Search,
	ExternalLink,
	Upload,
	User,
	Volume2,
} from "lucide-react";
import Link from "next/link";

interface Album {
	id: number;
	title: string;
	cover: string | null;
	cover_medium: string | null;
	cover_big: string | null;
	cover_xl: string | null;
	release_date: string;
	deezer_id: number;
	artist_id: number;
	artist_name: string;
	nb_tracks: number;
	duration: number;
	status: string;
	monitored: boolean;
	upgrade_allowed: boolean | null;
	has_file: boolean;
	file_path: string | null;
	file_size: number | null;
	record_type: string | null;
	upc: string | null;
	explicit_lyrics: boolean | null;
}

interface Track {
	id: number;
	title: string;
	duration: number;
	track_position: number;
	disk_number: number;
	preview: string | null;
	has_file: boolean;
	explicit_lyrics: boolean;
	artist_name: string;
}

interface FileInfo {
	file_path: string;
	file_name: string;
	file_size: number | null;
	quality: string | null;
	resolution: string | null;
	codec: string | null;
	audio_codec: string | null;
	audio_channels: string | null;
	container: string | null;
	bit_depth: string | null;
	hdr: boolean;
	created_at: string | null;
}

export default function AlbumDetailPage() {
	const params = useParams();
	const router = useRouter();
	const albumId = parseInt(params.id as string);
	const queryClient = useQueryClient();

	const [currentlyPlaying, setCurrentlyPlaying] = useState<number | null>(
		null,
	);
	const [showDeleteModal, setShowDeleteModal] = useState(false);
	const [showInteractiveSearch, setShowInteractiveSearch] = useState(false);
	const [showManualImport, setShowManualImport] = useState(false);
	const [volume, setVolume] = useState(0.7);
	const [currentTime, setCurrentTime] = useState(0);
	const [duration, setDuration] = useState(0);
	const audioRef = useRef<HTMLAudioElement | null>(null);

	const { data: album, isLoading: albumLoading } = useQuery({
		queryKey: ["album", albumId],
		queryFn: async () => {
			const response = await api.get(`/music/albums/${albumId}`);
			return response.data as Album;
		},
	});

	const { data: tracks, isLoading: tracksLoading } = useQuery({
		queryKey: ["tracks", albumId],
		queryFn: async () => {
			const response = await api.get(`/music/tracks?album_id=${albumId}`);
			return response.data as Track[];
		},
	});

	const { data: files } = useQuery({
		queryKey: ["files", "album", albumId],
		queryFn: async () => {
			const response = await api.get(`/files/album/${albumId}`);
			return response.data as { files: FileInfo[]; grab_mode?: string };
		},
		enabled: !!album?.has_file,
	});

	const addTracksMutation = useMutation({
		mutationFn: async () => {
			const response = await api.post(
				`/music/albums/${albumId}/add-tracks`,
			);
			return response.data;
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["tracks", albumId] });
			queryClient.invalidateQueries({ queryKey: ["album", albumId] });
		},
	});

	const searchDownloadMutation = useMutation({
		mutationFn: async () => {
			const response = await api.post(
				`/music/albums/${albumId}/search-download`,
			);
			return response.data;
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["album", albumId] });
		},
	});

	const toggleMonitoredMutation = useMutation({
		mutationFn: async (monitored: boolean) => {
			const response = await api.put(`/music/albums/${albumId}`, {
				monitored,
			});
			return response.data;
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["album", albumId] });
		},
	});

	const refreshMetadataMutation = useMutation({
		mutationFn: async () => {
			const response = await api.post(
				`/music/albums/${albumId}/refresh-metadata`,
			);
			return response.data;
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["album", albumId] });
		},
	});

	const deleteAlbumMutation = useMutation({
		mutationFn: async (deleteFiles: boolean) => {
			const response = await api.delete(
				`/music/albums/${albumId}/delete?delete_files=${deleteFiles}`,
			);
			return response.data;
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["albums"] });
			if (album?.artist_id) {
				router.push(`/music/artist/${album.artist_id}`);
			} else {
				router.push("/music");
			}
		},
	});

	const getCoverUrl = (album: Album) => {
		return (
			album.cover_xl ||
			album.cover_big ||
			album.cover_medium ||
			album.cover ||
			"/placeholder-poster.svg"
		);
	};

	const formatDuration = (seconds: number) => {
		if (!seconds) return "--:--";
		const mins = Math.floor(seconds / 60);
		const secs = seconds % 60;
		return `${mins}:${String(secs).padStart(2, "0")}`;
	};

	const formatTotalDuration = (seconds: number) => {
		if (!seconds) return "Unknown";
		const hours = Math.floor(seconds / 3600);
		const mins = Math.floor((seconds % 3600) / 60);
		if (hours > 0) {
			return `${hours}h ${mins}m`;
		}
		return `${mins}m`;
	};

	const getStatusBadge = (status: string, hasFile: boolean) => {
		if (hasFile) {
			return (
				<span className="px-3 py-1 text-sm rounded bg-green-500/20 text-green-400 border border-green-500/50 font-medium">
					Downloaded
				</span>
			);
		}
		if (status === "downloading") {
			return (
				<span className="px-3 py-1 text-sm rounded bg-blue-500/20 text-blue-400 border border-blue-500/50 font-medium">
					Downloading
				</span>
			);
		}
		if (status === "wanted") {
			return (
				<span className="px-3 py-1 text-sm rounded bg-yellow-500/20 text-yellow-400 border border-yellow-500/50 font-medium">
					Wanted
				</span>
			);
		}
		return (
			<span className="px-3 py-1 text-sm rounded bg-gray-500/20 text-gray-400 border border-gray-500/50 font-medium">
				{status}
			</span>
		);
	};

	const getTrackNumber = (track: Track) => {
		if (!track.track_position) return "-";
		const hasMultipleDiscs =
			tracks && tracks.some((t) => t.disk_number > 1);
		if (hasMultipleDiscs) {
			return `${track.disk_number || 1}-${track.track_position}`;
		}
		return track.track_position.toString();
	};

	const resetPlayback = () => {
		setCurrentTime(0);
		setDuration(0);
	};

	const handlePlayPreview = async (track: Track) => {
		if (!track.preview) return;

		if (currentlyPlaying === track.id) {
			audioRef.current?.pause();
			resetPlayback();
			setCurrentlyPlaying(null);
		} else {
			if (audioRef.current) {
				audioRef.current.pause();
			}
			resetPlayback();

			// Create audio without crossOrigin to avoid CORS issues with Deezer CDN
			const audio = new Audio(track.preview);
			audio.volume = volume;

			// Track time updates for progress bar
			audio.addEventListener("timeupdate", () => {
				setCurrentTime(audio.currentTime);
				setDuration(audio.duration || 30);
			});
			audio.addEventListener("loadedmetadata", () => {
				setDuration(audio.duration || 30);
			});
			audio.addEventListener("ended", () => {
				resetPlayback();
				setCurrentlyPlaying(null);
			});
			audio.addEventListener("error", () => {
				resetPlayback();
				setCurrentlyPlaying(null);
				console.error("Failed to load audio preview");
			});

			try {
				await audio.play();
				audioRef.current = audio;
				setCurrentlyPlaying(track.id);
			} catch (err) {
				console.error("Failed to play preview:", err);
				resetPlayback();
				setCurrentlyPlaying(null);
			}
		}
	};

	// Cleanup on unmount
	useEffect(() => {
		return () => {
			if (audioRef.current) {
				audioRef.current.pause();
			}
		};
	}, []);

	const handleVolumeChange = (newVolume: number) => {
		setVolume(newVolume);
		if (audioRef.current) {
			audioRef.current.volume = newVolume;
		}
	};

	const formatPlaybackTime = (seconds: number) => {
		const mins = Math.floor(seconds / 60);
		const secs = Math.floor(seconds % 60);
		return `${mins}:${String(secs).padStart(2, "0")}`;
	};

	const handleDeleteConfirm = (deleteFiles: boolean) => {
		setShowDeleteModal(false);
		deleteAlbumMutation.mutate(deleteFiles);
	};

	const handleMonitoringUpdate = (newState: {
		monitored: boolean;
		upgradeAllowed: boolean | null;
	}) => {
		queryClient.invalidateQueries({ queryKey: ["album", albumId] });
	};

	if (albumLoading) {
		return (
			<div className="min-h-screen">
				<PageHeader
					title="Loading..."
					description="Loading album details"
					gradientFrom="purple-600/10"
					gradientVia="pink-600/10"
					gradientTo="rose-600/10"
				/>
				<div className="container mx-auto px-6 py-8">
					<div className="flex items-center justify-center py-12">
						<div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
					</div>
				</div>
			</div>
		);
	}

	if (!album) {
		return (
			<div className="min-h-screen">
				<PageHeader
					title="Not Found"
					description="Album not found"
					gradientFrom="purple-600/10"
					gradientVia="pink-600/10"
					gradientTo="rose-600/10"
				/>
				<div className="container mx-auto px-6 py-8">
					<div className="text-center py-12">
						<p className="text-muted-foreground mb-4">
							Album not found
						</p>
						<Link
							href="/music"
							className="inline-flex items-center gap-2 px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition font-medium"
						>
							<ArrowLeft className="w-5 h-5" />
							Back to Music
						</Link>
					</div>
				</div>
			</div>
		);
	}

	const backLink = album.artist_id
		? `/music/artist/${album.artist_id}`
		: "/music";
	const backText = album.artist_id
		? `Back to ${album.artist_name}`
		: "Back to Music";

	return (
		<div className="min-h-screen">
			<PageHeader
				title={album.title}
				description={`by ${album.artist_name}`}
				gradientFrom="purple-600/10"
				gradientVia="pink-600/10"
				gradientTo="rose-600/10"
			>
				<Link
					href={backLink}
					className="flex items-center gap-2 px-4 py-2 bg-card text-foreground border-2 border-border rounded-lg hover:bg-accent transition font-medium"
				>
					<ArrowLeft className="w-4 h-4" />
					{backText}
				</Link>
			</PageHeader>

			<div className="container mx-auto px-6 py-8">
				<div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
					{/* Album Info Card */}
					<div className="lg:col-span-1 space-y-6">
						<div className="bg-card text-card-foreground rounded-lg shadow border-2 border-border overflow-hidden sticky top-8">
							<div className="relative aspect-square">
								<img
									src={getCoverUrl(album)}
									alt={album.title}
									className="w-full h-full object-cover"
								/>
								{album.monitored && (
									<div className="absolute top-4 right-4 bg-primary text-primary-foreground p-2 rounded-lg shadow-lg">
										<Eye className="w-5 h-5" />
									</div>
								)}
							</div>
							<div className="p-6 space-y-4">
								<div>
									<div className="flex items-center gap-2 mb-2">
										<h2 className="text-2xl font-bold">
											{album.title}
										</h2>
										{album.explicit_lyrics && (
											<span className="px-2 py-0.5 text-xs rounded bg-red-500/20 text-red-400 border border-red-500/50 font-bold">
												EXPLICIT
											</span>
										)}
									</div>
									{album.artist_id ? (
										<Link
											href={`/music/artist/${album.artist_id}`}
											className="flex items-center gap-2 text-primary hover:underline font-medium"
										>
											<User className="w-4 h-4" />
											{album.artist_name}
										</Link>
									) : (
										<p className="flex items-center gap-2 text-muted-foreground">
											<User className="w-4 h-4" />
											{album.artist_name}
										</p>
									)}
								</div>

								<div className="space-y-2 text-sm">
									<div className="flex justify-between">
										<span className="text-muted-foreground">
											Release Date:
										</span>
										<span className="font-medium">
											{album.release_date
												? new Date(
														album.release_date,
													).toLocaleDateString()
												: "Unknown"}
										</span>
									</div>
									<div className="flex justify-between">
										<span className="text-muted-foreground">
											Tracks:
										</span>
										<span className="font-medium">
											{album.nb_tracks || 0}
										</span>
									</div>
									<div className="flex justify-between">
										<span className="text-muted-foreground">
											Duration:
										</span>
										<span className="font-medium">
											{formatTotalDuration(
												album.duration,
											)}
										</span>
									</div>
									{album.record_type && (
										<div className="flex justify-between">
											<span className="text-muted-foreground">
												Type:
											</span>
											<span className="font-medium capitalize">
												{album.record_type}
											</span>
										</div>
									)}
									{album.upc && (
										<div className="flex justify-between">
											<span className="text-muted-foreground">
												UPC:
											</span>
											<span className="font-mono text-xs">
												{album.upc}
											</span>
										</div>
									)}
								</div>

								{/* Status & Monitoring */}
								<div className="py-3 border-y border-border space-y-3">
									<div className="flex justify-between items-center">
										<span className="text-sm text-muted-foreground">
											Status
										</span>
										{getStatusBadge(
											album.status,
											album.has_file,
										)}
									</div>
									<div className="flex justify-between items-center">
										<span className="text-sm text-muted-foreground">
											Monitoring
										</span>
										<MonitoringOptionsDropdown
											mediaType="album"
											mediaId={album.id}
											currentState={{
												monitored: album.monitored,
												upgradeAllowed:
													album.upgrade_allowed,
											}}
											onUpdate={handleMonitoringUpdate}
										/>
									</div>
								</div>

								<div className="space-y-2">
									<button
										onClick={() =>
											setShowInteractiveSearch(true)
										}
										className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition font-medium cursor-pointer"
									>
										<Search className="w-5 h-5" />
										Interactive Search
									</button>

									<button
										onClick={() =>
											searchDownloadMutation.mutate()
										}
										disabled={
											searchDownloadMutation.isPending ||
											album.status === "downloading"
										}
										className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition font-medium cursor-pointer"
									>
										<Download className="w-5 h-5" />
										{searchDownloadMutation.isPending
											? "Searching..."
											: "Auto Search & Download"}
									</button>

									<button
										onClick={() =>
											setShowManualImport(true)
										}
										className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-card text-foreground border-2 border-border rounded-lg hover:bg-accent transition font-medium cursor-pointer"
									>
										<Upload className="w-5 h-5" />
										Manual Import
									</button>

									<div className="flex gap-2">
										<button
											onClick={() =>
												refreshMetadataMutation.mutate()
											}
											disabled={
												refreshMetadataMutation.isPending
											}
											className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-card text-foreground border-2 border-border rounded-lg hover:bg-accent transition font-medium disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
										>
											<RefreshCw
												className={`w-5 h-5 ${refreshMetadataMutation.isPending ? "animate-spin" : ""}`}
											/>
											Refresh
										</button>
										<button
											onClick={() =>
												setShowDeleteModal(true)
											}
											className="flex items-center justify-center gap-2 px-4 py-3 bg-destructive text-destructive-foreground rounded-lg hover:opacity-90 transition font-medium cursor-pointer"
										>
											<Trash2 className="w-5 h-5" />
										</button>
									</div>
								</div>

								{/* External Links */}
								{album.deezer_id && (
									<div className="pt-4 border-t border-border">
										<h4 className="text-sm font-medium text-muted-foreground mb-2">
											External Links
										</h4>
										<a
											href={`https://www.deezer.com/album/${album.deezer_id}`}
											target="_blank"
											rel="noopener noreferrer"
											className="flex items-center gap-2 px-3 py-2 bg-muted hover:bg-muted/80 rounded-lg transition text-sm cursor-pointer"
										>
											<img
												src="https://www.deezer.com/favicon.ico"
												alt="Deezer"
												className="w-4 h-4"
											/>
											View on Deezer
											<ExternalLink className="w-3 h-3 text-muted-foreground ml-auto" />
										</a>
									</div>
								)}
							</div>
						</div>
					</div>

					{/* Right Column - Tracks & Info */}
					<div className="lg:col-span-2 space-y-6">
						{/* File Quality Info */}
						{album.has_file && (
							<FileQualityInfo
								mediaType="album"
								mediaId={album.id}
								files={files?.files || []}
								grabMode={files?.grab_mode}
							/>
						)}

						{/* Tags */}
						<TagsEditor mediaType="album" mediaId={album.id} />

						{/* Download History */}
						<DownloadHistoryPanel
							mediaType="album"
							mediaId={album.id}
						/>

						{/* Tracks Listing */}
						<div className="bg-card text-card-foreground rounded-lg shadow border-2 border-border overflow-hidden">
							<div className="p-6 border-b border-border">
								<div className="flex justify-between items-center">
									<h3 className="text-xl font-bold flex items-center gap-2">
										<Music2 className="w-6 h-6" />
										Track Listing
									</h3>
									{tracks && tracks.length === 0 && (
										<button
											onClick={() =>
												addTracksMutation.mutate()
											}
											disabled={
												addTracksMutation.isPending
											}
											className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition font-medium cursor-pointer"
										>
											<Download className="w-4 h-4" />
											{addTracksMutation.isPending
												? "Fetching..."
												: "Fetch Tracks from Deezer"}
										</button>
									)}
								</div>
							</div>

							{tracksLoading ? (
								<div className="p-12 text-center">
									<div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto" />
								</div>
							) : !tracks || tracks.length === 0 ? (
								<div className="p-12 text-center">
									<Music2 className="w-16 h-16 mx-auto mb-4 text-muted-foreground opacity-50" />
									<p className="text-muted-foreground mb-4">
										No tracks found for this album.
									</p>
									<button
										onClick={() =>
											addTracksMutation.mutate()
										}
										disabled={addTracksMutation.isPending}
										className="inline-flex items-center gap-2 px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition font-medium cursor-pointer"
									>
										<Download className="w-5 h-5" />
										{addTracksMutation.isPending
											? "Fetching from Deezer..."
											: "Fetch Tracks from Deezer"}
									</button>
								</div>
							) : (
								<div className="overflow-x-auto">
									<table className="w-full">
										<thead className="bg-accent/50">
											<tr>
												<th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
													#
												</th>
												<th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
													Title
												</th>
												<th className="px-6 py-3 text-center text-xs font-medium text-muted-foreground uppercase tracking-wider">
													<Clock className="w-4 h-4 inline" />
												</th>
												<th className="px-6 py-3 text-center text-xs font-medium text-muted-foreground uppercase tracking-wider">
													Preview
												</th>
												<th className="px-6 py-3 text-center text-xs font-medium text-muted-foreground uppercase tracking-wider">
													Status
												</th>
											</tr>
										</thead>
										<tbody className="divide-y divide-border">
											{tracks.map((track) => (
												<tr
													key={track.id}
													className="hover:bg-accent/30 transition"
												>
													<td className="px-6 py-4 whitespace-nowrap text-sm text-muted-foreground font-mono">
														{getTrackNumber(track)}
													</td>
													<td className="px-6 py-4">
														<div className="flex items-center gap-2">
															{track.explicit_lyrics && (
																<span className="px-1.5 py-0.5 text-xs rounded bg-red-500/20 text-red-400 border border-red-500/50 font-bold">
																	E
																</span>
															)}
															<span className="font-medium">
																{track.title}
															</span>
														</div>
														{track.artist_name &&
															track.artist_name !==
																album.artist_name && (
																<div className="text-xs text-muted-foreground mt-1">
																	{
																		track.artist_name
																	}
																</div>
															)}
													</td>
													<td className="px-6 py-4 whitespace-nowrap text-sm text-center font-mono">
														{formatDuration(
															track.duration,
														)}
													</td>
													<td className="px-6 py-4 whitespace-nowrap text-center">
														{track.preview ? (
															<button
																onClick={() =>
																	handlePlayPreview(
																		track,
																	)
																}
																className={`p-2 rounded-full transition cursor-pointer ${
																	currentlyPlaying ===
																	track.id
																		? "bg-primary text-primary-foreground"
																		: "bg-accent hover:bg-primary hover:text-primary-foreground"
																}`}
																title={
																	currentlyPlaying ===
																	track.id
																		? "Pause preview"
																		: "Play 30s preview"
																}
															>
																{currentlyPlaying ===
																track.id ? (
																	<Pause className="w-4 h-4" />
																) : (
																	<Play className="w-4 h-4" />
																)}
															</button>
														) : (
															<span className="text-xs text-muted-foreground">
																N/A
															</span>
														)}
													</td>
													<td className="px-6 py-4 whitespace-nowrap text-center">
														{track.has_file ? (
															<span className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded bg-green-500/20 text-green-400 border border-green-500/50 font-medium">
																<Download className="w-3 h-3" />
																Downloaded
															</span>
														) : (
															<span className="text-xs text-muted-foreground">
																-
															</span>
														)}
													</td>
												</tr>
											))}
										</tbody>
									</table>
								</div>
							)}

							{tracks && tracks.length > 0 && (
								<div className="px-6 py-4 bg-accent/30 border-t border-border space-y-3">
									{/* Audio Progress - only shown when playing */}
									{currentlyPlaying && (
										<div className="flex items-center gap-2">
											<span className="text-xs text-muted-foreground font-mono w-10">
												{formatPlaybackTime(
													currentTime,
												)}
											</span>
											<div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
												<div
													className="h-full bg-primary transition-all duration-100"
													style={{
														width: `${duration > 0 ? (currentTime / duration) * 100 : 0}%`,
													}}
												/>
											</div>
											<span className="text-xs text-muted-foreground font-mono w-10 text-right">
												{formatPlaybackTime(duration)}
											</span>
										</div>
									)}

									<div className="flex items-center justify-between text-sm">
										<div className="flex items-center gap-4">
											<span className="text-muted-foreground">
												<Disc3 className="w-4 h-4 inline mr-1" />
												{tracks.length} tracks
											</span>
											<span className="text-muted-foreground">
												<Clock className="w-4 h-4 inline mr-1" />
												{formatTotalDuration(
													tracks.reduce(
														(sum, t) =>
															sum +
															(t.duration || 0),
														0,
													),
												)}
											</span>
										</div>
										<div className="flex items-center gap-4">
											<div className="flex items-center gap-2">
												<Volume2 className="w-4 h-4 text-muted-foreground" />
												<input
													type="range"
													min="0"
													max="1"
													step="0.01"
													value={volume}
													onChange={(e) =>
														handleVolumeChange(
															parseFloat(
																e.target.value,
															),
														)
													}
													className="w-20 h-1.5 bg-muted rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-primary [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer [&::-moz-range-thumb]:w-3 [&::-moz-range-thumb]:h-3 [&::-moz-range-thumb]:bg-primary [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:cursor-pointer"
													title={`Volume: ${Math.round(volume * 100)}%`}
												/>
											</div>
											<div className="text-muted-foreground">
												{
													tracks.filter(
														(t) => t.has_file,
													).length
												}{" "}
												/ {tracks.length} downloaded
											</div>
										</div>
									</div>
								</div>
							)}
						</div>
					</div>
				</div>
			</div>

			{/* Modals */}
			<DeleteConfirmModal
				isOpen={showDeleteModal}
				onCancel={() => setShowDeleteModal(false)}
				onConfirm={handleDeleteConfirm}
				title={album.title}
				itemName="album"
				hasFiles={album.has_file}
			/>

			<InteractiveSearchModal
				isOpen={showInteractiveSearch}
				onClose={() => setShowInteractiveSearch(false)}
				mediaType="album"
				mediaId={album.id}
				mediaTitle={album.title}
				searchQuery={`${album.artist_name} ${album.title}`}
			/>

			<ManualImportModal
				isOpen={showManualImport}
				onClose={() => setShowManualImport(false)}
				mediaType="album"
				mediaId={album.id}
				mediaTitle={album.title}
				onImportComplete={() => {
					queryClient.invalidateQueries({
						queryKey: ["album", albumId],
					});
					queryClient.invalidateQueries({
						queryKey: ["files", "album", albumId],
					});
				}}
			/>
		</div>
	);
}
