"use client";

import { AlertCircle, CheckCircle, Download, X } from "lucide-react";
import type { IndexerTestResult } from "@/types/indexer";

const STAGE_LABELS: Record<string, string> = {
	config: "Configuration",
	connect: "Connection",
	auth: "Authentication",
	rate_limit: "Rate limit",
	http: "HTTP status",
	parse: "Parsing",
};

function formatSize(bytes: number | null): string {
	if (!bytes) return "";
	const units = ["B", "KB", "MB", "GB", "TB"];
	let size = bytes;
	let unit = 0;
	while (size >= 1024 && unit < units.length - 1) {
		size /= 1024;
		unit++;
	}
	return `${size.toFixed(1)} ${units[unit]}`;
}

interface IndexerTestPanelProps {
	result: IndexerTestResult;
	onClose?: () => void;
}

// The outcome of an indexer test, with each step, the exact failure, and the parsed results.
export default function IndexerTestPanel({
	result,
	onClose,
}: IndexerTestPanelProps) {
	return (
		<div className="p-4 rounded-lg border border-border bg-muted/20 space-y-3">
			<div className="flex items-center justify-between">
				<p className="text-sm font-semibold flex items-center gap-2">
					{result.ok ? (
						<CheckCircle className="w-4 h-4 text-green-500" />
					) : (
						<AlertCircle className="w-4 h-4 text-red-500" />
					)}
					{result.ok ? "Test passed" : "Test failed"}
					<span className="text-xs text-muted-foreground font-normal">
						{(result.duration_ms / 1000).toFixed(1)}s
					</span>
				</p>
				{onClose && (
					<button
						type="button"
						onClick={onClose}
						className="p-1.5 bg-muted rounded hover:bg-muted/80 transition cursor-pointer"
						title="Close"
					>
						<X className="w-3.5 h-3.5" />
					</button>
				)}
			</div>

			<div className="space-y-1">
				{result.steps.map((step, index) => (
					<div key={index} className="flex items-start gap-2 text-sm">
						{step.ok ? (
							<CheckCircle className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" />
						) : (
							<AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
						)}
						<span className="font-medium">{step.name}</span>
						<span className="text-muted-foreground break-all">
							{step.detail}
						</span>
					</div>
				))}
			</div>

			{result.error && (
				<div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-sm space-y-1">
					<p className="font-medium text-red-500">
						{STAGE_LABELS[result.error.stage] || result.error.stage}
						{result.error.status
							? ` (HTTP ${result.error.status})`
							: ""}
						{result.error.field
							? `, field ${result.error.field}`
							: ""}
					</p>
					<p className="text-muted-foreground break-all">
						{result.error.message}
					</p>
				</div>
			)}

			{result.results.length > 0 && (
				<div className="overflow-x-auto">
					<table className="w-full text-xs">
						<thead>
							<tr className="text-left text-muted-foreground border-b border-border">
								<th className="py-1 pr-3 font-medium">Title</th>
								<th className="py-1 pr-3 font-medium">Size</th>
								<th className="py-1 pr-3 font-medium">
									Seeders
								</th>
								<th className="py-1 pr-3 font-medium">
									Leechers
								</th>
								<th className="py-1 pr-3 font-medium">
									Published
								</th>
								<th className="py-1 pr-3 font-medium">
									Uploader
								</th>
								<th className="py-1 font-medium">Download</th>
							</tr>
						</thead>
						<tbody>
							{result.results.map((release, index) => (
								<tr
									key={index}
									className="border-b border-border"
								>
									<td className="py-1 pr-3 break-all">
										{release.title}
										{release.quality && (
											<span className="ml-2 px-2 py-0.5 bg-muted rounded">
												{release.quality}
											</span>
										)}
									</td>
									<td className="py-1 pr-3 whitespace-nowrap">
										{formatSize(release.size)}
									</td>
									<td className="py-1 pr-3">
										{release.seeders}
									</td>
									<td className="py-1 pr-3">
										{release.leechers}
									</td>
									<td className="py-1 pr-3 whitespace-nowrap">
										{release.publish_date
											? new Date(
													release.publish_date,
												).toLocaleDateString()
											: ""}
									</td>
									<td className="py-1 pr-3">
										{release.uploader || ""}
									</td>
									<td className="py-1">
										{release.has_download ? (
											<span title="Download link found">
												<Download className="w-3.5 h-3.5 text-green-500" />
											</span>
										) : (
											<span title="No download link">
												<X className="w-3.5 h-3.5 text-red-500" />
											</span>
										)}
									</td>
								</tr>
							))}
						</tbody>
					</table>
				</div>
			)}
		</div>
	);
}
