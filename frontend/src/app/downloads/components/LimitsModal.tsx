"use client";

import { useState } from "react";
import { X } from "lucide-react";
import type {
	Torrent,
	ShareLimitsInput,
	SpeedLimitsInput,
} from "../../../types/downloads";

interface LimitsModalProps {
	mode: "share" | "speed";
	torrent: Torrent;
	onClose: () => void;
	onSubmitShare?: (limits: ShareLimitsInput) => Promise<void>;
	onSubmitSpeed?: (limits: SpeedLimitsInput) => Promise<void>;
}

type LimitMode = "global" | "unlimited" | "custom";

function initialMode(value: number): LimitMode {
	if (value === -1) return "global";
	if (value <= -2) return "unlimited";
	return "custom";
}

function resolveValue(mode: LimitMode, custom: number): number {
	if (mode === "global") return -1;
	if (mode === "unlimited") return -2;
	return custom;
}

function LimitRow({
	label,
	mode,
	setMode,
	custom,
	setCustom,
	unit,
}: {
	label: string;
	mode: LimitMode;
	setMode: (m: LimitMode) => void;
	custom: number;
	setCustom: (n: number) => void;
	unit: string;
}) {
	return (
		<div>
			<label className="block text-sm font-medium mb-1">{label}</label>
			<div className="flex gap-2 items-center">
				<select
					value={mode}
					onChange={(e) => setMode(e.target.value as LimitMode)}
					className="px-3 py-2 rounded-lg bg-background border border-border text-sm focus:outline-none"
				>
					<option value="global">Global default</option>
					<option value="unlimited">Unlimited</option>
					<option value="custom">Custom</option>
				</select>
				{mode === "custom" && (
					<div className="flex items-center gap-1">
						<input
							type="number"
							min={0}
							step="any"
							value={custom}
							onChange={(e) =>
								setCustom(parseFloat(e.target.value) || 0)
							}
							className="w-28 px-3 py-2 rounded-lg bg-background border border-border text-sm focus:outline-none"
						/>
						<span className="text-xs text-muted-foreground">
							{unit}
						</span>
					</div>
				)}
			</div>
		</div>
	);
}

export default function LimitsModal({
	mode,
	torrent,
	onClose,
	onSubmitShare,
	onSubmitSpeed,
}: LimitsModalProps) {
	// Share-limit state
	const [ratioMode, setRatioMode] = useState<LimitMode>(
		initialMode(torrent.ratio_limit),
	);
	const [ratioCustom, setRatioCustom] = useState(
		torrent.ratio_limit > 0 ? torrent.ratio_limit : 1,
	);
	const [seedMode, setSeedMode] = useState<LimitMode>(
		initialMode(torrent.seeding_time_limit),
	);
	const [seedCustom, setSeedCustom] = useState(
		torrent.seeding_time_limit > 0 ? torrent.seeding_time_limit : 60,
	);
	const [inactiveMode, setInactiveMode] = useState<LimitMode>(
		initialMode(torrent.inactive_seeding_time_limit),
	);
	const [inactiveCustom, setInactiveCustom] = useState(
		torrent.inactive_seeding_time_limit > 0
			? torrent.inactive_seeding_time_limit
			: 30,
	);

	// Speed-limit state (stored in bytes/s, edited in KB/s)
	const [dlKb, setDlKb] = useState(
		Math.round((torrent.dl_limit || 0) / 1024),
	);
	const [upKb, setUpKb] = useState(
		Math.round((torrent.up_limit || 0) / 1024),
	);

	const [submitting, setSubmitting] = useState(false);

	const handleSubmit = async () => {
		setSubmitting(true);
		try {
			if (mode === "share" && onSubmitShare) {
				await onSubmitShare({
					ratio_limit: resolveValue(ratioMode, ratioCustom),
					seeding_time_limit: resolveValue(seedMode, seedCustom),
					inactive_seeding_time_limit: resolveValue(
						inactiveMode,
						inactiveCustom,
					),
				});
			} else if (mode === "speed" && onSubmitSpeed) {
				await onSubmitSpeed({
					download_limit: Math.max(0, Math.round(dlKb * 1024)),
					upload_limit: Math.max(0, Math.round(upKb * 1024)),
				});
			}
			onClose();
		} catch {
			setSubmitting(false);
		}
	};

	return (
		<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
			<div className="bg-card text-card-foreground rounded-lg shadow-xl w-full max-w-md">
				<div className="flex items-center justify-between p-4 border-b border-border">
					<h2 className="text-lg font-semibold">
						{mode === "share" ? "Seeding Limits" : "Speed Limits"}
					</h2>
					<button
						onClick={onClose}
						className="p-1 rounded hover:bg-accent cursor-pointer"
					>
						<X className="w-5 h-5" />
					</button>
				</div>
				<div className="p-4 space-y-4">
					<p className="text-xs text-muted-foreground truncate">
						{torrent.name}
					</p>
					{mode === "share" ? (
						<>
							<LimitRow
								label="Ratio limit"
								mode={ratioMode}
								setMode={setRatioMode}
								custom={ratioCustom}
								setCustom={setRatioCustom}
								unit="ratio"
							/>
							<LimitRow
								label="Seeding time limit"
								mode={seedMode}
								setMode={setSeedMode}
								custom={seedCustom}
								setCustom={setSeedCustom}
								unit="minutes"
							/>
							<LimitRow
								label="Inactive seeding time limit"
								mode={inactiveMode}
								setMode={setInactiveMode}
								custom={inactiveCustom}
								setCustom={setInactiveCustom}
								unit="minutes"
							/>
						</>
					) : (
						<div className="grid grid-cols-2 gap-3">
							<div>
								<label className="block text-sm font-medium mb-1">
									Download (KB/s)
								</label>
								<input
									type="number"
									min={0}
									value={dlKb}
									onChange={(e) =>
										setDlKb(parseInt(e.target.value) || 0)
									}
									className="w-full px-3 py-2 rounded-lg bg-background border border-border text-sm focus:outline-none"
								/>
								<p className="text-xs text-muted-foreground mt-1">
									0 = unlimited
								</p>
							</div>
							<div>
								<label className="block text-sm font-medium mb-1">
									Upload (KB/s)
								</label>
								<input
									type="number"
									min={0}
									value={upKb}
									onChange={(e) =>
										setUpKb(parseInt(e.target.value) || 0)
									}
									className="w-full px-3 py-2 rounded-lg bg-background border border-border text-sm focus:outline-none"
								/>
								<p className="text-xs text-muted-foreground mt-1">
									0 = unlimited
								</p>
							</div>
						</div>
					)}
				</div>
				<div className="flex justify-end gap-2 p-4 border-t border-border">
					<button
						onClick={onClose}
						className="px-4 py-2 rounded-lg border border-border hover:bg-accent transition text-sm cursor-pointer"
					>
						Cancel
					</button>
					<button
						onClick={handleSubmit}
						disabled={submitting}
						className="px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:opacity-90 transition text-sm disabled:opacity-50 cursor-pointer"
					>
						{submitting ? "Saving..." : "Save"}
					</button>
				</div>
			</div>
		</div>
	);
}
