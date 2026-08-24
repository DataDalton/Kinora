// Formatting helpers for download client displays.

export function formatBytes(bytes: number | null | undefined): string {
	if (!bytes || bytes <= 0) return "0 B";
	const k = 1024;
	const sizes = ["B", "KB", "MB", "GB", "TB", "PB"];
	const i = Math.min(
		Math.floor(Math.log(bytes) / Math.log(k)),
		sizes.length - 1,
	);
	return `${Math.round((bytes / Math.pow(k, i)) * 100) / 100} ${sizes[i]}`;
}

export function formatSpeed(bytesPerSec: number | null | undefined): string {
	if (!bytesPerSec || bytesPerSec <= 0) return "0 B/s";
	return `${formatBytes(bytesPerSec)}/s`;
}

export function formatEta(seconds: number | null | undefined): string {
	if (seconds === null || seconds === undefined || seconds < 0) return "∞";
	if (seconds === 0) return "0s";
	const days = Math.floor(seconds / 86400);
	const hours = Math.floor((seconds % 86400) / 3600);
	const minutes = Math.floor((seconds % 3600) / 60);
	const secs = Math.floor(seconds % 60);
	if (days > 0) return `${days}d ${hours}h`;
	if (hours > 0) return `${hours}h ${minutes}m`;
	if (minutes > 0) return `${minutes}m ${secs}s`;
	return `${secs}s`;
}

// Format a duration given in minutes into a compact label.
export function formatMinutes(minutes: number | null | undefined): string {
	if (minutes === null || minutes === undefined) return "—";
	if (minutes < 0) return "∞";
	return formatEta(minutes * 60);
}

export function formatRatio(ratio: number | null | undefined): string {
	if (ratio === null || ratio === undefined || ratio < 0) return "0.00";
	return ratio.toFixed(2);
}

// Interpret a share-limit value: -1 inherits global, -2 (or below) is unlimited.
export function describeShareLimit(
	value: number,
	unit: "ratio" | "minutes",
): string {
	if (value === -1) return "Global";
	if (value <= -2) return "Unlimited";
	if (unit === "ratio") return value.toFixed(2);
	return formatMinutes(value);
}

export function formatTimestamp(epoch: number | null | undefined): string {
	if (!epoch || epoch <= 0) return "N/A";
	return new Date(epoch * 1000).toLocaleString();
}
