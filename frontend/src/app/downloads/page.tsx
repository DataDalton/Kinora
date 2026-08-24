"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Gauge, Zap } from "lucide-react";
import { usePermissions } from "@/contexts/PermissionContext";
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
import type { Torrent, TorrentGroup } from "@/types/downloads";
import TorrentCard from "./components/TorrentCard";
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

type ToastState = { id: number; message: string; type: "success" | "error" };

export default function DownloadsPage() {
	const queryClient = useQueryClient();
	const { hasPermission } = usePermissions();
	const canControl = hasPermission("system.downloads");

	const [toasts, setToasts] = useState<ToastState[]>([]);
	const [showAdd, setShowAdd] = useState(false);
	const [deleteTarget, setDeleteTarget] = useState<Torrent | null>(null);
	const [shareTarget, setShareTarget] = useState<Torrent | null>(null);
	const [speedTarget, setSpeedTarget] = useState<Torrent | null>(null);
	const [showGlobalSpeed, setShowGlobalSpeed] = useState(false);
	const [rangeHours, setRangeHours] = useState(24);

	const notify = (message: string, type: "success" | "error" = "success") => {
		const id = Date.now() + Math.random();
		setToasts((t) => [...t, { id, message, type }]);
		setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3500);
	};

	const invalidate = () => {
		queryClient.invalidateQueries({ queryKey: ["downloads-torrents"] });
		queryClient.invalidateQueries({ queryKey: ["downloads-stats"] });
	};

	const { data: torrentsData, isLoading } = useQuery({
		queryKey: ["downloads-torrents"],
		queryFn: listTorrents,
		refetchInterval: 3000,
	});

	const { data: stats } = useQuery({
		queryKey: ["downloads-stats"],
		queryFn: getDownloadStats,
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
		notify("Torrent removed", "success");
	};

	const handleAltSpeed = async () => {
		try {
			const result = await toggleAltSpeed();
			invalidate();
			notify(
				result.alt_speed_enabled
					? "Alternative speed on"
					: "Alternative speed off",
				"success",
			);
		} catch {
			notify("Failed to toggle alt speed", "error");
		}
	};

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
					<ConnectionSafetyBanner
						canControl={canControl}
						notify={notify}
					/>

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
									className={`flex items-center gap-1.5 px-3 py-2 rounded-lg border text-sm transition cursor-pointer ${
										stats?.alt_speed_enabled
											? "bg-primary text-primary-foreground border-primary"
											: "border-border hover:bg-accent"
									}`}
								>
									<Zap className="w-4 h-4" /> Alt speed
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
														onChanged={invalidate}
														notify={notify}
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
						notify("Torrent added", "success");
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
						notify("Seeding limits updated", "success");
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
						notify("Speed limits updated", "success");
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
						notify("Global speed limits updated", "success");
					}}
				/>
			)}

			{/* Toasts */}
			<div className="fixed bottom-4 right-4 z-[60] space-y-2">
				{toasts.map((toast) => (
					<div
						key={toast.id}
						className={`px-4 py-3 rounded-lg shadow-lg text-sm text-white ${
							toast.type === "error"
								? "bg-destructive"
								: "bg-green-600"
						}`}
					>
						{toast.message}
					</div>
				))}
			</div>
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
