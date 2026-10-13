"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Gauge, Zap, Loader2 } from "lucide-react";
import { usePermissions } from "@/contexts/PermissionContext";
import { useToast } from "@/components/toast/ToastProvider";
import {
	listTorrents,
	getDownloadStats,
	getTransferHistory,
	deleteTorrent,
	addTorrent,
	setTorrentShareLimits,
	setTorrentSpeedLimits,
	setGlobalSpeedLimits,
	toggleAltSpeed,
} from "@/lib/api/downloads";
import type {
	DownloadStats,
	Torrent,
	TorrentGroup,
	TorrentsResponse,
} from "@/types/downloads";
import TorrentCard, { type TorrentAction } from "./components/TorrentCard";
import AddTorrentModal from "./components/AddTorrentModal";
import DeleteTorrentModal from "./components/DeleteTorrentModal";
import LimitsModal from "./components/LimitsModal";
import TransferChart from "./components/TransferChart";
import ConnectionSafetyBanner from "./components/ConnectionSafetyBanner";
import { formatSpeed } from "./components/format";

const GROUPS: { key: TorrentGroup; label: string }[] = [
	{ key: "downloading", label: "Downloading" },
	{ key: "seeding", label: "Seeding" },
	{ key: "queued", label: "Queued" },
	{ key: "paused", label: "Paused" },
];

const RANGES = [
	{ label: "6h", hours: 6 },
	{ label: "24h", hours: 24 },
	{ label: "7d", hours: 168 },
];

const TORRENTS_KEY = ["downloads-torrents"];
const STATS_KEY = ["downloads-stats"];
// How often the state is re-read while waiting for a control action to show up in
// qBittorrent, and how many reads happen before it is reported as not applied.
const CONFIRM_POLL_MS = 1_000;
const CONFIRM_MAX_READS = 10;
const ALT_SPEED_KEY = "alt-speed";
// Queries holding download history or a library item's status.
const LIBRARY_QUERY_KEYS = [
	"download-history",
	"movie",
	"movies",
	"show",
	"shows",
	"anime",
	"album",
	"albums",
];

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export default function DownloadsPage() {
	const queryClient = useQueryClient();
	const { hasPermission } = usePermissions();
	const canControl = hasPermission("system.downloads");

	const toast = useToast();
	const [showAdd, setShowAdd] = useState(false);
	const [deleteTarget, setDeleteTarget] = useState<Torrent | null>(null);
	const [shareTarget, setShareTarget] = useState<Torrent | null>(null);
	const [speedTarget, setSpeedTarget] = useState<Torrent | null>(null);
	const [showGlobalSpeed, setShowGlobalSpeed] = useState(false);
	const [rangeHours, setRangeHours] = useState(24);

	const invalidate = () => {
		queryClient.invalidateQueries({ queryKey: TORRENTS_KEY });
		queryClient.invalidateQueries({ queryKey: STATS_KEY });
	};

	// Action id in flight per pending key, a torrent hash or ALT_SPEED_KEY. The matching
	// controls stay disabled with a spinner until qBittorrent reports the new state.
	const [pendingActions, setPendingActions] = useState<
		Record<string, string>
	>({});
	// Mirrors pendingActions synchronously, so a second click in the same render cannot
	// start a duplicate request before the state update lands.
	const pendingKeys = useRef(new Set<string>());
	const mounted = useRef(true);
	useEffect(() => {
		mounted.current = true;
		return () => {
			mounted.current = false;
		};
	}, []);

	// Sends a control action, then re-reads fresh client state until reached() confirms
	// qBittorrent applied it or CONFIRM_MAX_READS reads pass without it. Actions with no observable
	// state pass reached as null and finish once the request succeeds. subject names what
	// the action applied to, such as a torrent, and is shown under the toast title.
	const runConfirmed = async (
		key: string,
		actionId: string,
		label: string,
		request: () => Promise<unknown>,
		reached: (() => Promise<boolean>) | null,
		successMessage: string,
		subject?: string,
	) => {
		if (pendingKeys.current.has(key)) return;
		pendingKeys.current.add(key);
		setPendingActions((current) => ({ ...current, [key]: actionId }));
		try {
			await request();
			if (reached) {
				let confirmed = await reached();
				for (
					let read = 1;
					!confirmed && mounted.current && read < CONFIRM_MAX_READS;
					read++
				) {
					await wait(CONFIRM_POLL_MS);
					confirmed = await reached();
				}
				if (!mounted.current) return;
				if (!confirmed) {
					toast.warning(`${label} was sent but not applied yet`, {
						description: subject
							? `qBittorrent has not applied it to ${subject} yet`
							: "qBittorrent has not applied it yet",
					});
					return;
				}
			}
			toast.success(successMessage, { description: subject });
		} catch (err: unknown) {
			toast.error(`${label} failed`, {
				description: [
					subject,
					err instanceof Error ? err.message : undefined,
				]
					.filter(Boolean)
					.join(". "),
			});
		} finally {
			pendingKeys.current.delete(key);
			setPendingActions((current) => {
				const next = { ...current };
				delete next[key];
				return next;
			});
			invalidate();
		}
	};

	// Reads the torrent list past the snapshot and stores it, so every card updates from
	// the same read. A torrent that is gone counts as reached, since nothing is left to wait on.
	const torrentReached =
		(hash: string, check: (torrent: Torrent) => boolean) => async () => {
			const fresh = await listTorrents(true);
			queryClient.setQueryData<TorrentsResponse>(TORRENTS_KEY, fresh);
			const latest = fresh.torrents.find((t) => t.hash === hash);
			return !latest || check(latest);
		};

	const runTorrentAction = (torrent: Torrent, action: TorrentAction) =>
		runConfirmed(
			torrent.hash,
			action.id,
			action.label,
			action.request,
			action.reached
				? torrentReached(torrent.hash, action.reached)
				: null,
			action.successMessage,
			torrent.name,
		);

	const { data: torrentsData, isLoading } = useQuery({
		queryKey: TORRENTS_KEY,
		queryFn: () => listTorrents(),
		refetchInterval: 3000,
	});

	const { data: stats } = useQuery({
		queryKey: STATS_KEY,
		queryFn: () => getDownloadStats(),
		refetchInterval: 3000,
	});

	const { data: history } = useQuery({
		queryKey: ["downloads-history", rangeHours],
		queryFn: () => getTransferHistory(rangeHours),
		refetchInterval: 60000,
		enabled: !!stats?.configured,
	});

	const torrents = torrentsData?.torrents ?? [];
	const configured = torrentsData?.configured ?? false;
	const grouped: Record<TorrentGroup, Torrent[]> = {
		downloading: [],
		seeding: [],
		queued: [],
		paused: [],
	};
	for (const t of torrents) grouped[t.group]?.push(t);

	const handleDelete = async (deleteFiles: boolean) => {
		if (!deleteTarget) return;
		await deleteTorrent(deleteTarget.hash, deleteFiles);
		invalidate();
		// Removing a torrent also changes its history row and its library item's status,
		// so pages showing either refetch instead of serving the cached copy.
		for (const key of LIBRARY_QUERY_KEYS) {
			queryClient.invalidateQueries({ queryKey: [key] });
		}
		toast.success(
			deleteFiles ? "Torrent and files removed" : "Torrent removed",
			{ description: deleteTarget.name },
		);
	};

	const handleAltSpeed = () => {
		const target = !stats?.alt_speed_enabled;
		runConfirmed(
			ALT_SPEED_KEY,
			"alt-speed",
			"Alternative speed",
			toggleAltSpeed,
			async () => {
				const fresh = await getDownloadStats(true);
				queryClient.setQueryData<DownloadStats>(STATS_KEY, fresh);
				return fresh.alt_speed_enabled === target;
			},
			target ? "Alternative speed on" : "Alternative speed off",
		);
	};
	const altSpeedPending = ALT_SPEED_KEY in pendingActions;

	return (
		<div className="container mx-auto px-6 py-8">
			{!configured && !isLoading ? (
				<div className="bg-card text-card-foreground rounded-lg shadow p-12 text-center">
					<h2 className="text-2xl font-bold mb-4">
						Download client not configured
					</h2>
					<p className="text-muted-foreground">
						Configure qBittorrent in Settings to monitor and control
						downloads here.
					</p>
				</div>
			) : isLoading ? (
				<div className="text-center py-12 text-muted-foreground">
					Loading downloads...
				</div>
			) : (
				<>
					<ConnectionSafetyBanner canControl={canControl} />

					{/* Toolbar */}
					<div className="flex flex-wrap items-center justify-between gap-3 mb-6">
						<div className="flex gap-4 text-sm">
							<span className="text-blue-500 font-medium">
								↓ {formatSpeed(stats?.download_speed ?? 0)}
							</span>
							<span className="text-emerald-500 font-medium">
								↑ {formatSpeed(stats?.upload_speed ?? 0)}
							</span>
						</div>
						{canControl && (
							<div className="flex gap-2">
								<button
									onClick={handleAltSpeed}
									disabled={altSpeedPending}
									className={`flex items-center gap-1.5 px-3 py-2 rounded-lg border text-sm transition cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed ${
										stats?.alt_speed_enabled
											? "bg-primary text-primary-foreground border-primary"
											: "border-border hover:bg-accent"
									}`}
								>
									{altSpeedPending ? (
										<Loader2 className="w-4 h-4 animate-spin" />
									) : (
										<Zap className="w-4 h-4" />
									)}{" "}
									Alt speed
								</button>
								<button
									onClick={() => setShowGlobalSpeed(true)}
									className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-border hover:bg-accent text-sm transition cursor-pointer"
								>
									<Gauge className="w-4 h-4" /> Global limits
								</button>
								<button
									onClick={() => setShowAdd(true)}
									className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-primary text-primary-foreground hover:opacity-90 transition text-sm cursor-pointer"
								>
									<Plus className="w-4 h-4" /> Add Torrent
								</button>
							</div>
						)}
					</div>

					{/* Stats + history */}
					{stats?.configured && (
						<div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-8">
							<div className="lg:col-span-2 bg-card text-card-foreground rounded-lg shadow p-4">
								<div className="flex items-center justify-between mb-2">
									<p className="text-sm font-medium">
										Transfer history
									</p>
									<div className="flex gap-1">
										{RANGES.map((r) => (
											<button
												key={r.hours}
												onClick={() =>
													setRangeHours(r.hours)
												}
												className={`px-2 py-1 rounded text-xs cursor-pointer transition ${
													rangeHours === r.hours
														? "bg-primary text-primary-foreground"
														: "bg-muted hover:bg-muted/70 text-muted-foreground"
												}`}
											>
												{r.label}
											</button>
										))}
									</div>
								</div>
								<TransferChart
									data={history ?? []}
									rangeHours={rangeHours}
								/>
							</div>
							<div className="bg-card text-card-foreground rounded-lg shadow p-4 flex flex-col justify-center">
								<div className="grid grid-cols-2 gap-3 text-center">
									<StatTile
										label="Downloading"
										value={stats.counts?.downloading ?? 0}
									/>
									<StatTile
										label="Seeding"
										value={stats.counts?.seeding ?? 0}
									/>
									<StatTile
										label="Queued"
										value={stats.counts?.queued ?? 0}
									/>
									<StatTile
										label="Paused"
										value={stats.counts?.paused ?? 0}
									/>
								</div>
								<div className="mt-4 pt-3 border-t border-border space-y-1 text-xs">
									<div className="flex justify-between">
										<span className="text-muted-foreground">
											DL limit
										</span>
										<span>
											{stats.download_rate_limit
												? formatSpeed(
														stats.download_rate_limit,
													)
												: "Unlimited"}
										</span>
									</div>
									<div className="flex justify-between">
										<span className="text-muted-foreground">
											UL limit
										</span>
										<span>
											{stats.upload_rate_limit
												? formatSpeed(
														stats.upload_rate_limit,
													)
												: "Unlimited"}
										</span>
									</div>
									<div className="flex justify-between">
										<span className="text-muted-foreground">
											Connection
										</span>
										<span className="capitalize">
											{stats.connection_status}
										</span>
									</div>
								</div>
							</div>
						</div>
					)}

					{/* Grouped torrents */}
					{torrents.length === 0 ? (
						<div className="bg-card text-card-foreground rounded-lg shadow p-12 text-center">
							<h2 className="text-2xl font-bold mb-2">
								No active torrents
							</h2>
							<p className="text-muted-foreground">
								Downloads appear here as they are added.
							</p>
						</div>
					) : (
						GROUPS.map(
							(group) =>
								grouped[group.key].length > 0 && (
									<div key={group.key} className="mb-8">
										<h2 className="text-xl font-bold mb-4">
											{group.label} (
											{grouped[group.key].length})
										</h2>
										<div className="space-y-3">
											{grouped[group.key].map(
												(torrent) => (
													<TorrentCard
														key={torrent.hash}
														torrent={torrent}
														canControl={canControl}
														pendingAction={
															pendingActions[
																torrent.hash
															]
														}
														onAction={(action) =>
															runTorrentAction(
																torrent,
																action,
															)
														}
														onDelete={() =>
															setDeleteTarget(
																torrent,
															)
														}
														onEditShareLimits={() =>
															setShareTarget(
																torrent,
															)
														}
														onEditSpeedLimits={() =>
															setSpeedTarget(
																torrent,
															)
														}
													/>
												),
											)}
										</div>
									</div>
								),
						)
					)}
				</>
			)}

			{/* Modals */}
			{showAdd && (
				<AddTorrentModal
					onClose={() => setShowAdd(false)}
					onSubmit={async (input) => {
						await addTorrent(input);
						invalidate();
						toast.success("Torrent added");
					}}
				/>
			)}
			{deleteTarget && (
				<DeleteTorrentModal
					torrentName={deleteTarget.name}
					onClose={() => setDeleteTarget(null)}
					onConfirm={handleDelete}
				/>
			)}
			{shareTarget && (
				<LimitsModal
					mode="share"
					torrent={shareTarget}
					onClose={() => setShareTarget(null)}
					onSubmitShare={async (limits) => {
						await setTorrentShareLimits(shareTarget.hash, limits);
						invalidate();
						toast.success("Seeding limits updated", {
							description: shareTarget.name,
						});
					}}
				/>
			)}
			{speedTarget && (
				<LimitsModal
					mode="speed"
					torrent={speedTarget}
					onClose={() => setSpeedTarget(null)}
					onSubmitSpeed={async (limits) => {
						await setTorrentSpeedLimits(speedTarget.hash, limits);
						invalidate();
						toast.success("Speed limits updated", {
							description: speedTarget.name,
						});
					}}
				/>
			)}
			{showGlobalSpeed && stats?.configured && (
				<LimitsModal
					mode="speed"
					torrent={
						{
							name: "Global speed limits",
							dl_limit: stats.download_rate_limit ?? 0,
							up_limit: stats.upload_rate_limit ?? 0,
						} as Torrent
					}
					onClose={() => setShowGlobalSpeed(false)}
					onSubmitSpeed={async (limits) => {
						await setGlobalSpeedLimits(limits);
						invalidate();
						toast.success("Global speed limits updated");
					}}
				/>
			)}
		</div>
	);
}

function StatTile({ label, value }: { label: string; value: number }) {
	return (
		<div>
			<p className="text-2xl font-bold">{value}</p>
			<p className="text-xs text-muted-foreground">{label}</p>
		</div>
	);
}
