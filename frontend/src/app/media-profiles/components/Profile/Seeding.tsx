"use client";

import { MediaProfileFormData } from "../types";

interface SeedingProps {
	formData: MediaProfileFormData;
	setFormData: (data: MediaProfileFormData) => void;
}

// A seeding override input: "Inherit" leaves the value null (uses global default),
// "Custom" reveals a number input.
function OverrideRow({
	label,
	description,
	value,
	onChange,
	unit,
	step,
}: {
	label: string;
	description: string;
	value: number | null;
	onChange: (v: number | null) => void;
	unit: string;
	step?: string;
}) {
	const isCustom = value !== null;
	return (
		<div className="p-4 bg-muted/50 rounded-lg border border-border">
			<label className="block text-sm font-semibold mb-1">{label}</label>
			<p className="text-xs text-muted-foreground mb-3">{description}</p>
			<div className="flex gap-2 items-center">
				<button
					type="button"
					onClick={() => onChange(null)}
					className={`px-3 py-2 rounded-lg text-sm font-medium transition cursor-pointer ${
						!isCustom
							? "bg-primary text-primary-foreground"
							: "bg-muted text-muted-foreground hover:bg-muted/80"
					}`}
				>
					Inherit global
				</button>
				<button
					type="button"
					onClick={() => onChange(isCustom ? value : 0)}
					className={`px-3 py-2 rounded-lg text-sm font-medium transition cursor-pointer ${
						isCustom
							? "bg-primary text-primary-foreground"
							: "bg-muted text-muted-foreground hover:bg-muted/80"
					}`}
				>
					Custom
				</button>
				{isCustom && (
					<div className="flex items-center gap-1">
						<input
							type="number"
							min={0}
							step={step || "1"}
							value={value ?? 0}
							onChange={(e) =>
								onChange(parseFloat(e.target.value) || 0)
							}
							className="w-28 px-3 py-2 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary text-sm"
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

export default function Seeding({ formData, setFormData }: SeedingProps) {
	return (
		<div className="space-y-6">
			<p className="text-sm text-muted-foreground">
				Override the global download-client seeding defaults for media
				using this profile. Leave values on{" "}
				<span className="font-medium">Inherit global</span> to follow
				the client-wide settings.
			</p>

			<OverrideRow
				label="Ratio limit"
				description="Stop seeding after reaching this upload/download ratio."
				value={formData.seed_ratio_limit}
				onChange={(v) =>
					setFormData({ ...formData, seed_ratio_limit: v })
				}
				unit="ratio"
				step="0.1"
			/>
			<OverrideRow
				label="Seeding time limit"
				description="Stop seeding after this many minutes of total seeding time."
				value={formData.seed_time_limit}
				onChange={(v) =>
					setFormData({
						...formData,
						seed_time_limit: v === null ? null : Math.round(v),
					})
				}
				unit="minutes"
			/>
			<OverrideRow
				label="Inactive seeding time limit"
				description="Stop seeding after this many minutes with no upload activity."
				value={formData.inactive_seed_time_limit}
				onChange={(v) =>
					setFormData({
						...formData,
						inactive_seed_time_limit:
							v === null ? null : Math.round(v),
					})
				}
				unit="minutes"
			/>

			<button
				type="button"
				role="switch"
				aria-checked={formData.seed_then_cleanup}
				onClick={() =>
					setFormData({
						...formData,
						seed_then_cleanup: !formData.seed_then_cleanup,
					})
				}
				className="w-full text-left p-4 bg-muted/50 rounded-lg border border-border hover:bg-muted/80 transition cursor-pointer"
			>
				<div className="flex items-center justify-between gap-4">
					<div>
						<span className="text-sm font-semibold">
							Seed then clean up
						</span>
						<p className="text-xs text-muted-foreground mt-1">
							Once seeding goals (and any tracker minimums) are
							met, remove the torrent. The hardlinked library copy
							is retained.
						</p>
					</div>
					<span
						className={`relative inline-flex h-6 w-11 flex-shrink-0 items-center rounded-full transition-colors ${
							formData.seed_then_cleanup
								? "bg-primary"
								: "bg-muted"
						}`}
					>
						<span
							className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
								formData.seed_then_cleanup
									? "translate-x-6"
									: "translate-x-1"
							}`}
						/>
					</span>
				</div>
			</button>

			<div className="p-4 bg-muted/50 rounded-lg border border-border">
				<label className="block text-sm font-semibold mb-1">
					Stalled auto-recovery
				</label>
				<p className="text-xs text-muted-foreground mb-3">
					When a download stalls or fails, blocklist it and search for
					the next best release matching this profile.
				</p>
				<div className="flex gap-2">
					<button
						type="button"
						onClick={() =>
							setFormData({ ...formData, auto_recovery: null })
						}
						className={`px-3 py-2 rounded-lg text-sm font-medium transition cursor-pointer ${
							formData.auto_recovery === null
								? "bg-primary text-primary-foreground"
								: "bg-muted text-muted-foreground hover:bg-muted/80"
						}`}
					>
						Inherit global
					</button>
					<button
						type="button"
						onClick={() =>
							setFormData({ ...formData, auto_recovery: true })
						}
						className={`px-3 py-2 rounded-lg text-sm font-medium transition cursor-pointer ${
							formData.auto_recovery === true
								? "bg-primary text-primary-foreground"
								: "bg-muted text-muted-foreground hover:bg-muted/80"
						}`}
					>
						Enabled
					</button>
					<button
						type="button"
						onClick={() =>
							setFormData({ ...formData, auto_recovery: false })
						}
						className={`px-3 py-2 rounded-lg text-sm font-medium transition cursor-pointer ${
							formData.auto_recovery === false
								? "bg-primary text-primary-foreground"
								: "bg-muted text-muted-foreground hover:bg-muted/80"
						}`}
					>
						Disabled
					</button>
				</div>
			</div>
		</div>
	);
}
