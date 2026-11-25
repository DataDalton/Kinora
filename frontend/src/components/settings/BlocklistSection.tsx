"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Ban, Globe, Hash, Search, Trash2, User } from "lucide-react";
import { api } from "@/lib/api";
import PageHeader from "@/components/PageHeader";
import ConfirmModal from "@/components/ConfirmModal";
import { useToast } from "@/components/toast/ToastProvider";

interface BlocklistEntry {
	id: number;
	media_type: string;
	media_id: number;
	media_title: string | null;
	release_title: string;
	reason: string | null;
	blocked_at: string;
	info_hash: string | null;
	scope: string;
}

type ScopeFilter = "all" | "every-item" | "one-item";

const MEDIA_TYPE_LABELS: Record<string, string> = {
	movie: "Movie",
	show: "TV Show",
	anime: "Anime",
	album: "Album",
	manual: "Manual add",
};

const MEDIA_TYPE_PATHS: Record<string, string> = {
	movie: "/movies",
	show: "/shows",
	anime: "/anime",
	album: "/music/album",
};

const SCOPE_FILTERS: { id: ScopeFilter; name: string }[] = [
	{ id: "all", name: "All" },
	{ id: "every-item", name: "Failed validation" },
	{ id: "one-item", name: "Blocklisted by hand" },
];

// Every blocklisted release. Entries scoped to all items are torrents that failed
// validation, blocked by hash for every item. The rest apply to one item, by title.
export default function BlocklistSection() {
	const queryClient = useQueryClient();
	const toast = useToast();
	const [search, setSearch] = useState("");
	const [scopeFilter, setScopeFilter] = useState<ScopeFilter>("all");
	const [pendingRemoval, setPendingRemoval] = useState<BlocklistEntry | null>(
		null,
	);

	const { data: entries = [], isLoading } = useQuery({
		queryKey: ["blocklist"],
		queryFn: async () => {
			const response = await api.get("/blocklist/", {
				params: { limit: 500 },
			});
			return response.data as BlocklistEntry[];
		},
	});

	const removeMutation = useMutation({
		mutationFn: async (entry: BlocklistEntry) => {
			await api.delete(`/blocklist/${entry.id}`);
			return entry;
		},
		onSuccess: (entry) => {
			toast.success("Removed from blocklist", {
				description: entry.release_title,
			});
			queryClient.invalidateQueries({ queryKey: ["blocklist"] });
		},
		onError: (error: any) => {
			toast.error("Couldn't remove entry", {
				description: error.response?.data?.detail,
			});
		},
	});

	const everyItemCount = entries.filter((e) => e.scope === "all").length;
	const oneItemCount = entries.length - everyItemCount;

	const visibleEntries = useMemo(() => {
		const query = search.trim().toLowerCase();
		return entries.filter((entry) => {
			if (scopeFilter === "every-item" && entry.scope !== "all") {
				return false;
			}
			if (scopeFilter === "one-item" && entry.scope === "all") {
				return false;
			}
			return (
				!query ||
				entry.release_title.toLowerCase().includes(query) ||
				(entry.media_title || "").toLowerCase().includes(query)
			);
		});
	}, [entries, search, scopeFilter]);

	const appliesTo = (entry: BlocklistEntry) => {
		if (entry.scope === "all") {
			return (
				<span className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs bg-destructive/20 text-destructive">
					<Globe className="w-3 h-3" />
					All items
				</span>
			);
		}
		const label = MEDIA_TYPE_LABELS[entry.media_type] || entry.media_type;
		const path = MEDIA_TYPE_PATHS[entry.media_type];
		const name = entry.media_title || `${label} #${entry.media_id}`;
		return (
			<div className="flex flex-col gap-1">
				<span className="inline-flex w-fit items-center gap-1 px-2 py-1 rounded text-xs bg-muted">
					<Ban className="w-3 h-3" />
					{label}
				</span>
				{path ? (
					<Link
						href={`${path}/${entry.media_id}`}
						className="text-sm text-primary hover:underline"
					>
						{name}
					</Link>
				) : (
					<span className="text-sm">{name}</span>
				)}
			</div>
		);
	};

	return (
		<div>
			<PageHeader
				title="Blocklist"
				description="Releases that search and RSS skip. Torrents that failed validation are blocked for every item by their hash. Releases blocklisted by hand apply to one item."
				gradientFrom="red-600/10"
				gradientVia="orange-600/10"
				gradientTo="amber-600/10"
			/>

			<div className="p-8">
				<div className="max-w-6xl mx-auto">
					{/* Overview Cards */}
					<div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
						<div className="bg-card border border-border rounded-lg p-4">
							<div className="flex items-center gap-3">
								<div className="p-2 bg-primary/10 rounded-lg">
									<Ban className="w-6 h-6 text-primary" />
								</div>
								<div>
									<div className="text-2xl font-bold">
										{isLoading ? "-" : entries.length}
									</div>
									<div className="text-sm text-muted-foreground">
										Blocklisted
									</div>
								</div>
							</div>
						</div>
						<div className="bg-card border border-border rounded-lg p-4">
							<div className="flex items-center gap-3">
								<div className="p-2 bg-red-500/10 rounded-lg">
									<Globe className="w-6 h-6 text-red-500" />
								</div>
								<div>
									<div className="text-2xl font-bold text-red-500">
										{isLoading ? "-" : everyItemCount}
									</div>
									<div className="text-sm text-muted-foreground">
										Failed validation, all items
									</div>
								</div>
							</div>
						</div>
						<div className="bg-card border border-border rounded-lg p-4">
							<div className="flex items-center gap-3">
								<div className="p-2 bg-yellow-500/10 rounded-lg">
									<User className="w-6 h-6 text-yellow-500" />
								</div>
								<div>
									<div className="text-2xl font-bold text-yellow-500">
										{isLoading ? "-" : oneItemCount}
									</div>
									<div className="text-sm text-muted-foreground">
										Blocklisted by hand, one item
									</div>
								</div>
							</div>
						</div>
					</div>

					{/* Search and Filters */}
					<div className="flex flex-col md:flex-row gap-4 mb-6">
						<div className="flex-1 relative">
							<Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
							<input
								type="text"
								placeholder="Search releases and titles..."
								value={search}
								onChange={(e) => setSearch(e.target.value)}
								className="w-full pl-12 pr-4 py-3 bg-card border-2 border-border rounded-lg focus:outline-none focus:border-primary transition-colors"
							/>
						</div>
						<div className="flex gap-2">
							{SCOPE_FILTERS.map((filter) => (
								<button
									key={filter.id}
									type="button"
									onClick={() => setScopeFilter(filter.id)}
									className={`px-4 py-2 rounded-lg font-medium transition-colors cursor-pointer whitespace-nowrap ${
										scopeFilter === filter.id
											? "bg-primary text-primary-foreground"
											: "bg-muted hover:bg-muted/80 text-foreground"
									}`}
								>
									{filter.name}
								</button>
							))}
						</div>
					</div>

					{/* Blocklist Table */}
					{isLoading ? (
						<div className="text-center py-8 text-muted-foreground">
							Loading blocklist...
						</div>
					) : visibleEntries.length === 0 ? (
						<div className="text-center py-12 bg-card border border-border rounded-lg">
							<Ban className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
							<p className="text-muted-foreground">
								{entries.length === 0
									? "Nothing is blocklisted"
									: "No entries match this search"}
							</p>
						</div>
					) : (
						<div className="bg-card border border-border rounded-lg overflow-x-auto">
							<table className="w-full">
								<thead className="bg-muted">
									<tr>
										<th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider">
											Release
										</th>
										<th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider">
											Applies To
										</th>
										<th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider">
											Hash
										</th>
										<th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider">
											Blocked
										</th>
										<th className="px-4 py-3" />
									</tr>
								</thead>
								<tbody className="divide-y divide-border">
									{visibleEntries.map((entry) => (
										<tr
											key={entry.id}
											className="hover:bg-muted/30"
										>
											<td className="px-4 py-3 max-w-md">
												<div
													className="font-medium truncate"
													title={entry.release_title}
												>
													{entry.release_title}
												</div>
												{entry.reason && (
													<div className="text-xs text-destructive mt-1">
														{entry.reason}
													</div>
												)}
											</td>
											<td className="px-4 py-3 whitespace-nowrap">
												{appliesTo(entry)}
											</td>
											<td className="px-4 py-3 whitespace-nowrap">
												{entry.info_hash ? (
													<code
														className="inline-flex items-center gap-1 text-xs bg-muted px-2 py-1 rounded"
														title={entry.info_hash}
													>
														<Hash className="w-3 h-3" />
														{entry.info_hash.slice(
															0,
															12,
														)}
													</code>
												) : (
													<span className="text-sm text-muted-foreground">
														By title
													</span>
												)}
											</td>
											<td className="px-4 py-3 whitespace-nowrap text-sm text-muted-foreground">
												{new Date(
													entry.blocked_at,
												).toLocaleString()}
											</td>
											<td className="px-4 py-3 whitespace-nowrap text-right">
												<button
													type="button"
													onClick={() =>
														setPendingRemoval(entry)
													}
													disabled={
														removeMutation.isPending
													}
													className="p-2 rounded-lg hover:bg-destructive/10 hover:text-destructive transition cursor-pointer disabled:opacity-50"
													title="Remove from the blocklist"
												>
													<Trash2 className="w-4 h-4" />
												</button>
											</td>
										</tr>
									))}
								</tbody>
							</table>
						</div>
					)}
				</div>
			</div>

			<ConfirmModal
				isOpen={pendingRemoval !== null}
				title="Remove from blocklist"
				message={
					pendingRemoval?.scope === "all"
						? `${pendingRemoval?.release_title} failed validation. Removing it lets search, RSS and manual adds download this torrent again for every item.`
						: `Search and RSS will be able to download ${pendingRemoval?.release_title} again.`
				}
				confirmText="Remove"
				variant="danger"
				onConfirm={() => {
					if (pendingRemoval) {
						removeMutation.mutate(pendingRemoval);
					}
					setPendingRemoval(null);
				}}
				onCancel={() => setPendingRemoval(null)}
			/>
		</div>
	);
}
