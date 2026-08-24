"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, RotateCcw, Link2, Magnet } from "lucide-react";
import { usePermissions } from "@/contexts/PermissionContext";
import { listSources, reAddSource } from "@/lib/api/downloads";

// Toast ids come from a counter so render stays free of impure calls.
let toastSequence = 0;

export default function SourceArchivePage() {
	const { hasPermission } = usePermissions();
	const canManage = hasPermission("system.downloads");
	const [search, setSearch] = useState("");
	const [query, setQuery] = useState("");
	const [busyId, setBusyId] = useState<number | null>(null);
	const [toasts, setToasts] = useState<
		{ id: number; message: string; type: "success" | "error" }[]
	>([]);

	const notify = (message: string, type: "success" | "error" = "success") => {
		const id = ++toastSequence;
		setToasts((t) => [...t, { id, message, type }]);
		setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3500);
	};

	const {
		data: sources,
		isLoading,
		refetch,
	} = useQuery({
		queryKey: ["download-sources", query],
		queryFn: () => listSources(query || undefined),
	});

	const handleReAdd = async (id: number) => {
		setBusyId(id);
		try {
			await reAddSource(id);
			notify("Re-added to download client", "success");
			refetch();
		} catch (err: unknown) {
			notify(
				err instanceof Error ? err.message : "Failed to re-add",
				"error",
			);
		} finally {
			setBusyId(null);
		}
	};

	return (
		<div className="container mx-auto px-6 py-8 max-w-4xl">
			<div className="mb-6">
				<h1 className="text-xl font-bold">Source Archive</h1>
				<p className="text-sm text-muted-foreground">
					Every grabbed release&apos;s magnet and .torrent, ready to
					re-add
				</p>
			</div>

			<div>
				{!canManage ? (
					<div className="bg-card rounded-lg shadow p-12 text-center text-muted-foreground">
						You do not have permission to view the source archive.
					</div>
				) : (
					<>
						<form
							onSubmit={(e) => {
								e.preventDefault();
								setQuery(search.trim());
							}}
							className="flex gap-2 mb-6"
						>
							<div className="relative flex-1">
								<Search className="w-4 h-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
								<input
									value={search}
									onChange={(e) => setSearch(e.target.value)}
									placeholder="Search by release title..."
									className="w-full pl-10 pr-4 py-2.5 rounded-lg bg-background border border-border text-sm focus:outline-none"
								/>
							</div>
							<button
								type="submit"
								className="px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:opacity-90 text-sm cursor-pointer"
							>
								Search
							</button>
						</form>

						{isLoading ? (
							<div className="text-center py-12 text-muted-foreground">
								Loading...
							</div>
						) : !sources || sources.length === 0 ? (
							<div className="bg-card rounded-lg shadow p-12 text-center">
								<h2 className="text-xl font-bold mb-2">
									No stored sources
								</h2>
								<p className="text-muted-foreground">
									Grabbed releases and their magnet/.torrent
									links appear here.
								</p>
							</div>
						) : (
							<div className="space-y-2">
								{sources.map((s) => (
									<div
										key={s.id}
										className="bg-card text-card-foreground rounded-lg shadow p-4 flex items-center justify-between gap-3"
									>
										<div className="min-w-0">
											<p className="font-medium text-sm truncate">
												{s.torrent_title}
											</p>
											<div className="flex gap-3 text-xs text-muted-foreground mt-1 flex-wrap items-center">
												{s.media_type && (
													<span className="capitalize px-2 py-0.5 bg-muted rounded">
														{s.media_type}
													</span>
												)}
												{s.indexer && (
													<span>{s.indexer}</span>
												)}
												{s.quality && (
													<span>{s.quality}</span>
												)}
												{s.status && (
													<span>· {s.status}</span>
												)}
												{s.magnet_link && (
													<Magnet
														className="w-3.5 h-3.5"
														aria-label="magnet available"
													/>
												)}
												{s.torrent_url && (
													<Link2
														className="w-3.5 h-3.5"
														aria-label="torrent url available"
													/>
												)}
											</div>
										</div>
										<button
											onClick={() => handleReAdd(s.id)}
											disabled={busyId === s.id}
											className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-border hover:bg-accent text-sm cursor-pointer flex-shrink-0 disabled:opacity-50"
										>
											<RotateCcw className="w-4 h-4" />{" "}
											Re-add
										</button>
									</div>
								))}
							</div>
						)}
					</>
				)}
			</div>

			<div className="fixed bottom-4 right-4 z-[60] space-y-2">
				{toasts.map((toast) => (
					<div
						key={toast.id}
						className={`px-4 py-3 rounded-lg shadow-lg text-sm text-white ${toast.type === "error" ? "bg-destructive" : "bg-green-600"}`}
					>
						{toast.message}
					</div>
				))}
			</div>
		</div>
	);
}
