"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Download, ArrowRight } from "lucide-react";
import { api } from "@/lib/api";
import PageHeader from "@/components/PageHeader";
import BlocklistActions from "@/components/BlocklistActions";
import { usePermissions } from "@/contexts/PermissionContext";
import { getDownloadStats } from "@/lib/api/downloads";

interface Download {
	id: number;
	media_id: number;
	media_type: string;
	torrent_hash: string;
	torrent_title: string;
	indexer: string;
	quality: string;
	size: number;
	status: string;
	progress: number;
	download_client: string;
	grab_mode?: string;
	started_at: string;
	completed_at: string | null;
	error_message: string | null;
}

export default function ActivityPage() {
	const { hasPermission } = usePermissions();
	const canViewDownloads = hasPermission("system.downloads");

	const { data: downloads, isLoading } = useQuery({
		queryKey: ["download-history"],
		queryFn: async () => {
			try {
				const response = await api.get("/download-history", {
					params: { limit: 50 },
				});
				return response.data.downloads || [];
			} catch (error) {
				return [];
			}
		},
		refetchInterval: 5000,
	});

	const { data: clientStats } = useQuery({
		queryKey: ["downloads-stats-widget"],
		queryFn: getDownloadStats,
		refetchInterval: 5000,
		enabled: canViewDownloads,
	});

	const formatBytes = (bytes: number) => {
		if (!bytes || bytes === 0) return "0 B";
		const k = 1024;
		const sizes = ["B", "KB", "MB", "GB"];
		const i = Math.floor(Math.log(bytes) / Math.log(k));
		return (
			Math.round((bytes / Math.pow(k, i)) * 100) / 100 + " " + sizes[i]
		);
	};

	const formatDate = (dateString: string) => {
		if (!dateString) return "N/A";
		return new Date(dateString).toLocaleString();
	};

	const getStatusBadge = (status: string) => {
		const colors: any = {
			downloading: "bg-blue-100 text-blue-800",
			processing: "bg-blue-100 text-blue-800",
			completed: "bg-green-100 text-green-800",
			failed: "bg-red-100 text-red-800",
			pending: "bg-yellow-100 text-yellow-800",
		};

		return (
			<span
				className={`px-2 py-1 text-xs rounded ${colors[status] || "bg-gray-100 text-gray-800"}`}
			>
				{status}
			</span>
		);
	};

	const activeDownloads =
		downloads?.filter(
			(d: Download) =>
				d.status === "downloading" || d.status === "processing",
		) || [];
	const completedDownloads =
		downloads?.filter((d: Download) => d.status === "completed") || [];
	const failedDownloads =
		downloads?.filter((d: Download) => d.status === "failed") || [];

	return (
		<div className="min-h-screen">
			<PageHeader
				title="Activity"
				description="Monitor your download progress and history"
				gradientFrom="orange-600/10"
				gradientVia="red-600/10"
				gradientTo="pink-600/10"
			/>

			{/* Content Section */}
			<div className="container mx-auto px-6 py-8">
				{canViewDownloads && clientStats?.configured && (
					<Link
						href="/downloads"
						className="flex items-center justify-between bg-card text-card-foreground rounded-lg shadow p-4 mb-6 hover:bg-accent/50 transition"
					>
						<div className="flex items-center gap-4">
							<Download className="w-5 h-5 text-primary" />
							<div className="flex gap-4 text-sm flex-wrap">
								<span>
									<span className="font-semibold">
										{clientStats.counts?.downloading ?? 0}
									</span>{" "}
									downloading
								</span>
								<span>
									<span className="font-semibold">
										{clientStats.counts?.seeding ?? 0}
									</span>{" "}
									seeding
								</span>
								<span className="text-blue-500">
									↓{" "}
									{formatBytes(
										clientStats.download_speed ?? 0,
									)}
									/s
								</span>
								<span className="text-emerald-500">
									↑{" "}
									{formatBytes(clientStats.upload_speed ?? 0)}
									/s
								</span>
							</div>
						</div>
						<span className="flex items-center gap-1 text-sm text-muted-foreground">
							Manage <ArrowRight className="w-4 h-4" />
						</span>
					</Link>
				)}
				{isLoading ? (
					<div className="text-center py-12">Loading activity...</div>
				) : (
					<>
						{activeDownloads.length > 0 && (
							<div className="mb-8">
								<h2 className="text-2xl font-bold mb-4">
									Active Downloads ({activeDownloads.length})
								</h2>
								<div className="space-y-3">
									{activeDownloads.map(
										(download: Download) => (
											<div
												key={download.id}
												className="bg-card text-card-foreground rounded-lg shadow p-4"
											>
												<div className="flex justify-between items-start mb-2">
													<div className="flex-1">
														<h3 className="font-semibold">
															{
																download.torrent_title
															}
														</h3>
														<div className="flex gap-3 text-sm text-muted-foreground mt-1">
															<span className="px-2 py-0.5 bg-muted rounded">
																{
																	download.indexer
																}
															</span>
															{download.grab_mode ===
																"manual" && (
																<span className="px-2 py-0.5 bg-purple-500/20 text-purple-500 rounded">
																	Manual
																</span>
															)}
															<span>
																{
																	download.quality
																}
															</span>
															<span>
																{formatBytes(
																	download.size,
																)}
															</span>
														</div>
													</div>
													{getStatusBadge(
														download.status,
													)}
												</div>
												<div className="flex items-center gap-4">
													<div className="flex-1 bg-secondary rounded-full h-2">
														<div
															className="bg-primary h-2 rounded-full transition-all"
															style={{
																width: `${download.progress || 0}%`,
															}}
														/>
													</div>
													<span className="text-sm font-medium min-w-[4rem] text-right">
														{(
															download.progress ||
															0
														).toFixed(1)}
														%
													</span>
												</div>
												<div className="text-xs text-muted-foreground mt-2">
													Started:{" "}
													{formatDate(
														download.started_at,
													)}
												</div>
											</div>
										),
									)}
								</div>
							</div>
						)}

						{completedDownloads.length > 0 && (
							<div className="mb-8">
								<h2 className="text-2xl font-bold mb-4">
									Completed ({completedDownloads.length})
								</h2>
								<div className="space-y-2">
									{completedDownloads
										.slice(0, 10)
										.map((download: Download) => (
											<div
												key={download.id}
												className="bg-card text-card-foreground rounded-lg shadow p-4"
											>
												<div className="flex justify-between items-start">
													<div className="flex-1">
														<h3 className="font-semibold text-sm">
															{
																download.torrent_title
															}
														</h3>
														<div className="flex gap-3 text-xs text-muted-foreground mt-1">
															<span className="px-2 py-0.5 bg-muted rounded">
																{
																	download.indexer
																}
															</span>
															{download.grab_mode ===
																"manual" && (
																<span className="px-2 py-0.5 bg-purple-500/20 text-purple-500 rounded">
																	Manual
																</span>
															)}
															<span>
																{
																	download.quality
																}
															</span>
															<span>
																{formatBytes(
																	download.size,
																)}
															</span>
															<span>
																Completed:{" "}
																{formatDate(
																	download.completed_at ||
																		"",
																)}
															</span>
														</div>
													</div>
													{getStatusBadge(
														download.status,
													)}
												</div>
											</div>
										))}
								</div>
							</div>
						)}

						{failedDownloads.length > 0 && (
							<div className="mb-8">
								<h2 className="text-2xl font-bold mb-4">
									Failed ({failedDownloads.length})
								</h2>
								<div className="space-y-2">
									{failedDownloads.map(
										(download: Download) => (
											<div
												key={download.id}
												className="bg-card text-card-foreground rounded-lg shadow p-4"
											>
												<div className="flex justify-between items-start">
													<div className="flex-1">
														<h3 className="font-semibold text-sm">
															{
																download.torrent_title
															}
														</h3>
														{download.error_message && (
															<p className="text-xs text-destructive mt-1">
																{
																	download.error_message
																}
															</p>
														)}
														<div className="flex gap-3 text-xs text-muted-foreground mt-1">
															<span className="px-2 py-0.5 bg-muted rounded">
																{
																	download.indexer
																}
															</span>
															{download.grab_mode ===
																"manual" && (
																<span className="px-2 py-0.5 bg-purple-500/20 text-purple-500 rounded">
																	Manual
																</span>
															)}
															<span>
																{formatDate(
																	download.started_at,
																)}
															</span>
														</div>
													</div>
													<div className="flex flex-col items-end gap-2">
														{getStatusBadge(
															download.status,
														)}
														<BlocklistActions
															mediaType={
																download.media_type
															}
															mediaId={
																download.media_id
															}
															releaseTitle={
																download.torrent_title
															}
														/>
													</div>
												</div>
											</div>
										),
									)}
								</div>
							</div>
						)}

						{downloads && downloads.length === 0 && (
							<div className="bg-card text-card-foreground rounded-lg shadow p-12 text-center">
								<h2 className="text-2xl font-bold mb-4">
									No Download Activity
								</h2>
								<p className="text-muted-foreground">
									Downloads will appear here once you start
									adding media to your library
								</p>
							</div>
						)}
					</>
				)}
			</div>
		</div>
	);
}
