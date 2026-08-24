"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
	Play,
	Pause,
	Trash2,
	RefreshCw,
	Radio,
	Zap,
	UploadCloud,
	ArrowDownUp,
	ChevronUp,
	ChevronDown,
	Gauge,
	Timer,
	Users,
	CheckCircle2,
	XCircle,
	Loader2,
} from "lucide-react";
import type { Torrent, ValidationStep } from "../../../types/downloads";
import {
	pauseTorrent,
	resumeTorrent,
	recheckTorrent,
	reannounceTorrent,
	setForceStart,
	setSuperSeeding,
	setSequentialDownload,
	queueAction,
	getTorrentDetail,
} from "../../../lib/api/downloads";
import {
	formatBytes,
	formatSpeed,
	formatEta,
	formatRatio,
	describeShareLimit,
} from "./format";
import PieceMap from "./PieceMap";

interface TorrentCardProps {
	torrent: Torrent;
	canControl: boolean;
	onChanged: () => void;
	notify: (message: string, type?: "success" | "error") => void;
	onDelete: () => void;
	onEditShareLimits: () => void;
	onEditSpeedLimits: () => void;
}

const STATE_COLORS: Record<string, string> = {
	downloading: "bg-blue-500/15 text-blue-500",
	seeding: "bg-green-500/15 text-green-500",
	paused: "bg-gray-500/15 text-gray-400",
	checking: "bg-yellow-500/15 text-yellow-500",
	error: "bg-red-500/15 text-red-500",
	queued: "bg-purple-500/15 text-purple-400",
	completed: "bg-green-500/15 text-green-500",
};

const VALIDATION_STEPS: { key: ValidationStep; label: string }[] = [
	{ key: "waiting_metadata", label: "Metadata" },
	{ key: "detecting_files", label: "Detect files" },
	{ key: "checking_extensions", label: "Check types" },
	{ key: "resolving", label: "Resolve" },
];

function ControlButton({
	icon: Icon,
	label,
	onClick,
	active,
	disabled,
	danger,
}: {
	icon: React.ComponentType<{ className?: string }>;
	label: string;
	onClick: () => void;
	active?: boolean;
	disabled?: boolean;
	danger?: boolean;
}) {
	return (
		<button
			onClick={onClick}
			disabled={disabled}
			title={label}
			aria-label={label}
			className={`p-2 rounded-lg border transition text-sm cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed ${
				active
					? "bg-primary text-primary-foreground border-primary"
					: danger
						? "border-border hover:bg-destructive/10 hover:text-destructive"
						: "border-border hover:bg-accent"
			}`}
		>
			<Icon className="w-4 h-4" />
		</button>
	);
}

function ValidationPanel({ torrent }: { torrent: Torrent }) {
	const step = torrent.validation_step;
	const report = torrent.validation_report;
	if (!step) return null;

	const terminalIndex =
		step === "passed" || step === "failed" || step === "pending"
			? VALIDATION_STEPS.length
			: VALIDATION_STEPS.findIndex((s) => s.key === step);

	return (
		<div className="mt-3 rounded-lg border border-border bg-background/50 p-3">
			<div className="flex items-center gap-2 mb-3">
				{step === "passed" ? (
					<CheckCircle2 className="w-4 h-4 text-green-500" />
				) : step === "failed" ? (
					<XCircle className="w-4 h-4 text-destructive" />
				) : (
					<Loader2 className="w-4 h-4 text-primary animate-spin" />
				)}
				<span className="text-sm font-medium">Validation</span>
				{report?.message && (
					<span className="text-xs text-muted-foreground truncate">
						{report.message}
					</span>
				)}
			</div>

			<div className="flex items-center gap-1 mb-3">
				{VALIDATION_STEPS.map((s, idx) => {
					const done = idx < terminalIndex || step === "passed";
					const current = s.key === step;
					const failedHere =
						step === "failed" && idx >= terminalIndex;
					return (
						<div
							key={s.key}
							className="flex items-center gap-1 flex-1"
						>
							<div
								className={`h-1.5 flex-1 rounded-full ${
									failedHere
										? "bg-destructive"
										: done
											? "bg-primary"
											: current
												? "bg-primary/50"
												: "bg-secondary"
								}`}
								title={s.label}
							/>
						</div>
					);
				})}
			</div>

			{report &&
				(report.valid_files.length > 0 ||
					report.invalid_files.length > 0 ||
					report.forbidden_files.length > 0) && (
					<div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
						<FileList
							title="Allowed"
							color="text-green-500"
							files={report.valid_files}
						/>
						<FileList
							title="Excluded"
							color="text-yellow-500"
							files={report.invalid_files}
						/>
						<FileList
							title="Forbidden"
							color="text-destructive"
							files={report.forbidden_files}
						/>
					</div>
				)}
		</div>
	);
}

function FileList({
	title,
	color,
	files,
}: {
	title: string;
	color: string;
	files: string[];
}) {
	return (
		<div>
			<p className={`font-medium mb-1 ${color}`}>
				{title} ({files.length})
			</p>
			<ul className="space-y-0.5 max-h-24 overflow-y-auto">
				{files.slice(0, 20).map((f, i) => (
					<li
						key={i}
						className="text-muted-foreground truncate"
						title={f}
					>
						{f.split("/").pop()}
					</li>
				))}
				{files.length > 20 && (
					<li className="text-muted-foreground">
						+{files.length - 20} more
					</li>
				)}
			</ul>
		</div>
	);
}

export default function TorrentCard({
	torrent,
	canControl,
	onChanged,
	notify,
	onDelete,
	onEditShareLimits,
	onEditSpeedLimits,
}: TorrentCardProps) {
	const [expanded, setExpanded] = useState(false);
	const [busy, setBusy] = useState(false);

	const { data: detail } = useQuery({
		queryKey: ["torrent-detail", torrent.hash],
		queryFn: () => getTorrentDetail(torrent.hash),
		enabled: expanded,
		refetchInterval: expanded ? 3000 : false,
	});

	const isPaused = torrent.state === "paused";
	const isSeeding = torrent.state === "seeding";
	const progressPct = Math.round((torrent.progress || 0) * 1000) / 10;

	const run = async (fn: () => Promise<void>, message: string) => {
		if (busy) return;
		setBusy(true);
		try {
			await fn();
			onChanged();
			notify(message, "success");
		} catch (err: unknown) {
			notify(
				err instanceof Error ? err.message : "Action failed",
				"error",
			);
		} finally {
			setBusy(false);
		}
	};

	return (
		<div className="bg-card text-card-foreground rounded-lg shadow p-4">
			<div className="flex justify-between items-start gap-3 mb-2">
				<div className="flex-1 min-w-0">
					<div className="flex items-center gap-2 flex-wrap">
						<h3 className="font-semibold text-sm truncate max-w-full">
							{torrent.name}
						</h3>
						<span
							className={`px-2 py-0.5 text-xs rounded ${STATE_COLORS[torrent.state] || "bg-muted"}`}
						>
							{torrent.state}
						</span>
						{torrent.media_type && (
							<span className="px-2 py-0.5 text-xs rounded bg-muted capitalize">
								{torrent.media_type}
							</span>
						)}
						{torrent.force_start && (
							<span className="px-2 py-0.5 text-xs rounded bg-amber-500/15 text-amber-500">
								force
							</span>
						)}
						{torrent.super_seeding && (
							<span className="px-2 py-0.5 text-xs rounded bg-fuchsia-500/15 text-fuchsia-500">
								super-seed
							</span>
						)}
					</div>
					<div className="flex gap-3 text-xs text-muted-foreground mt-1 flex-wrap">
						{torrent.indexer && (
							<span className="px-2 py-0.5 bg-muted rounded">
								{torrent.indexer}
							</span>
						)}
						{torrent.quality && <span>{torrent.quality}</span>}
						<span>{formatBytes(torrent.size)}</span>
						{torrent.category && <span>· {torrent.category}</span>}
					</div>
				</div>
				<button
					onClick={() => setExpanded((e) => !e)}
					className="p-1 rounded hover:bg-accent cursor-pointer flex-shrink-0"
					aria-label={expanded ? "Collapse" : "Expand"}
				>
					{expanded ? (
						<ChevronUp className="w-5 h-5" />
					) : (
						<ChevronDown className="w-5 h-5" />
					)}
				</button>
			</div>

			{/* Progress */}
			<div className="flex items-center gap-3 mb-2">
				<div className="flex-1 bg-secondary rounded-full h-2 overflow-hidden">
					<div
						className={`h-2 rounded-full transition-all ${isSeeding ? "bg-green-500" : "bg-primary"}`}
						style={{ width: `${progressPct}%` }}
					/>
				</div>
				<span className="text-sm font-medium min-w-[3.5rem] text-right">
					{progressPct.toFixed(1)}%
				</span>
			</div>

			{/* Metrics */}
			<div className="flex gap-4 text-xs text-muted-foreground flex-wrap">
				<span className="text-blue-500">
					↓ {formatSpeed(torrent.download_speed)}
				</span>
				<span className="text-emerald-500">
					↑ {formatSpeed(torrent.upload_speed)}
				</span>
				<span className="flex items-center gap-1">
					<Gauge className="w-3 h-3" /> {formatRatio(torrent.ratio)}
					<span className="opacity-60">
						/ {describeShareLimit(torrent.ratio_limit, "ratio")}
					</span>
				</span>
				<span className="flex items-center gap-1">
					<Timer className="w-3 h-3" /> {formatEta(torrent.eta)}
				</span>
				<span className="flex items-center gap-1">
					<Users className="w-3 h-3" /> {torrent.num_complete}/
					{torrent.num_incomplete} swarm
				</span>
				<span>avail {torrent.availability.toFixed(2)}</span>
				<span>▲ {formatBytes(torrent.uploaded)}</span>
			</div>

			{torrent.validation_step && <ValidationPanel torrent={torrent} />}

			{/* Controls */}
			{canControl && (
				<div className="flex flex-wrap gap-1.5 mt-3">
					{isPaused ? (
						<ControlButton
							icon={Play}
							label="Resume"
							disabled={busy}
							onClick={() =>
								run(
									() => resumeTorrent(torrent.hash),
									"Resumed",
								)
							}
						/>
					) : (
						<ControlButton
							icon={Pause}
							label="Pause"
							disabled={busy}
							onClick={() =>
								run(() => pauseTorrent(torrent.hash), "Paused")
							}
						/>
					)}
					<ControlButton
						icon={RefreshCw}
						label="Recheck"
						disabled={busy}
						onClick={() =>
							run(
								() => recheckTorrent(torrent.hash),
								"Rechecking",
							)
						}
					/>
					<ControlButton
						icon={Radio}
						label="Reannounce"
						disabled={busy}
						onClick={() =>
							run(
								() => reannounceTorrent(torrent.hash),
								"Reannounced",
							)
						}
					/>
					<ControlButton
						icon={Zap}
						label="Force start"
						active={torrent.force_start}
						disabled={busy}
						onClick={() =>
							run(
								() =>
									setForceStart(
										torrent.hash,
										!torrent.force_start,
									),
								torrent.force_start
									? "Force-start off"
									: "Force-start on",
							)
						}
					/>
					<ControlButton
						icon={UploadCloud}
						label="Super seeding"
						active={torrent.super_seeding}
						disabled={busy}
						onClick={() =>
							run(
								() =>
									setSuperSeeding(
										torrent.hash,
										!torrent.super_seeding,
									),
								torrent.super_seeding
									? "Super-seed off"
									: "Super-seed on",
							)
						}
					/>
					<ControlButton
						icon={ArrowDownUp}
						label="Sequential download"
						active={torrent.sequential_download}
						disabled={busy}
						onClick={() =>
							run(
								() =>
									setSequentialDownload(
										torrent.hash,
										!torrent.sequential_download,
									),
								"Toggled sequential",
							)
						}
					/>
					<button
						onClick={onEditShareLimits}
						disabled={busy}
						className="px-2.5 py-2 rounded-lg border border-border hover:bg-accent transition text-xs cursor-pointer disabled:opacity-40"
						title="Seeding limits"
					>
						Seed limits
					</button>
					<button
						onClick={onEditSpeedLimits}
						disabled={busy}
						className="px-2.5 py-2 rounded-lg border border-border hover:bg-accent transition text-xs cursor-pointer disabled:opacity-40"
						title="Speed limits"
					>
						Speed
					</button>
					<div className="flex gap-1">
						<ControlButton
							icon={ChevronUp}
							label="Queue up"
							disabled={busy}
							onClick={() =>
								run(
									() => queueAction(torrent.hash, "up"),
									"Moved up",
								)
							}
						/>
						<ControlButton
							icon={ChevronDown}
							label="Queue down"
							disabled={busy}
							onClick={() =>
								run(
									() => queueAction(torrent.hash, "down"),
									"Moved down",
								)
							}
						/>
					</div>
					<ControlButton
						icon={Trash2}
						label="Remove"
						danger
						disabled={busy}
						onClick={onDelete}
					/>
				</div>
			)}

			{/* Detail */}
			{expanded && (
				<div className="mt-4 pt-4 border-t border-border space-y-4">
					<div>
						<p className="text-xs font-medium mb-2 text-muted-foreground">
							Pieces
						</p>
						<PieceMap pieces={detail?.piece_states || []} />
					</div>

					{detail?.files && detail.files.length > 0 && (
						<div>
							<p className="text-xs font-medium mb-2 text-muted-foreground">
								Files ({detail.files.length})
							</p>
							<div className="space-y-1 max-h-56 overflow-y-auto">
								{detail.files.map((file, i) => (
									<div
										key={i}
										className="flex items-center gap-2 text-xs"
									>
										<span
											className="flex-1 truncate"
											title={file.name}
										>
											{file.name.split("/").pop()}
										</span>
										<span className="text-muted-foreground w-16 text-right">
											{formatBytes(file.size)}
										</span>
										<div className="w-24 bg-secondary rounded-full h-1.5 overflow-hidden">
											<div
												className="h-1.5 bg-primary"
												style={{
													width: `${Math.round((file.progress || 0) * 100)}%`,
												}}
											/>
										</div>
									</div>
								))}
							</div>
						</div>
					)}

					{detail?.trackers && detail.trackers.length > 0 && (
						<div>
							<p className="text-xs font-medium mb-2 text-muted-foreground">
								Trackers
							</p>
							<div className="space-y-1 max-h-40 overflow-y-auto">
								{detail.trackers
									.filter(
										(t) =>
											t.url && t.url.startsWith("http"),
									)
									.map((t, i) => (
										<div
											key={i}
											className="flex items-center gap-2 text-xs"
										>
											<span
												className="flex-1 truncate"
												title={t.url}
											>
												{t.url}
											</span>
											<span className="text-muted-foreground">
												{t.msg || `status ${t.status}`}
											</span>
										</div>
									))}
							</div>
						</div>
					)}

					<div className="text-xs text-muted-foreground">
						Save path:{" "}
						<span className="text-foreground">
							{torrent.save_path || "N/A"}
						</span>
					</div>
				</div>
			)}
		</div>
	);
}
