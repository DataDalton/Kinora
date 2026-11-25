"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
	AlertCircle,
	AlertTriangle,
	CheckCircle,
	Circle,
	FlaskConical,
	Loader2,
	Lock,
	Pencil,
	Plus,
	Rss,
	Search,
	Server,
	Trash2,
} from "lucide-react";
import { useToast } from "@/components/toast/ToastProvider";
import ConfirmModal from "@/components/ConfirmModal";
import PageHeader from "@/components/PageHeader";
import {
	deleteIndexer,
	getIndexerKinds,
	getIndexers,
	getIndexerTemplates,
	setIndexerToggles,
	testIndexer,
	validationErrors,
} from "@/lib/api/indexers";
import IndexerEditor, { SCOPES, TRUST_TIERS, Toggle } from "./IndexerEditor";
import IndexerTestPanel from "./IndexerTestPanel";
import type {
	CustomIndexer,
	IndexerHealthStatus,
	IndexerTestResult,
} from "@/types/indexer";

const HEALTH: Record<
	IndexerHealthStatus,
	{ label: string; icon: typeof CheckCircle; color: string }
> = {
	ok: { label: "Healthy", icon: CheckCircle, color: "text-green-500" },
	warning: {
		label: "Recent errors",
		icon: AlertTriangle,
		color: "text-yellow-500",
	},
	failing: { label: "Unreachable", icon: AlertCircle, color: "text-red-500" },
	disabled: { label: "Off", icon: Circle, color: "text-gray-400" },
	untested: { label: "Not tested", icon: Circle, color: "text-gray-400" },
};

const TIER_COLORS: Record<string, string> = {
	open: "bg-muted",
	balanced: "bg-yellow-500/10 text-yellow-500",
	trusted: "bg-green-500/10 text-green-500",
};

// Lists the user-defined indexers with their health, and adds, edits, tests and deletes them.
interface IndexersSectionProps {
	// False on the standalone indexers page, which draws its own header.
	showHeader?: boolean;
}

export default function IndexersSection({
	showHeader = true,
}: IndexersSectionProps = {}) {
	const queryClient = useQueryClient();
	const toast = useToast();
	const [editing, setEditing] = useState<CustomIndexer | "new" | null>(null);
	const [deleting, setDeleting] = useState<CustomIndexer | null>(null);
	const [testResults, setTestResults] = useState<
		Record<number, IndexerTestResult>
	>({});
	const [testingId, setTestingId] = useState<number | null>(null);

	const { data: indexers, isLoading } = useQuery({
		queryKey: ["custom-indexers"],
		queryFn: getIndexers,
	});
	const { data: kinds } = useQuery({
		queryKey: ["custom-indexer-kinds"],
		queryFn: getIndexerKinds,
		staleTime: Infinity,
	});
	const { data: templates } = useQuery({
		queryKey: ["custom-indexer-templates"],
		queryFn: getIndexerTemplates,
		staleTime: Infinity,
	});

	const refresh = () =>
		queryClient.invalidateQueries({ queryKey: ["custom-indexers"] });

	const toggleMutation = useMutation({
		mutationFn: async ({
			indexer,
			toggles,
		}: {
			indexer: CustomIndexer;
			toggles: { enable_search?: boolean; enable_rss?: boolean };
		}) => setIndexerToggles(indexer.id, toggles),
		onSuccess: refresh,
		onError: (error) =>
			toast.error("Couldn't change the indexer", {
				description: validationErrors(error).join(". "),
			}),
	});

	const deleteMutation = useMutation({
		mutationFn: async (indexer: CustomIndexer) => deleteIndexer(indexer.id),
		onSuccess: (_result, indexer) => {
			toast.success("Indexer deleted", { description: indexer.name });
			setDeleting(null);
			refresh();
		},
		onError: (error) =>
			toast.error("Couldn't delete the indexer", {
				description: validationErrors(error).join(". "),
			}),
	});

	const runTest = async (indexer: CustomIndexer) => {
		setTestingId(indexer.id);
		try {
			const result = await testIndexer(indexer.id);
			setTestResults((current) => ({ ...current, [indexer.id]: result }));
			refresh();
		} catch (error) {
			toast.error("Couldn't run the test", {
				description: validationErrors(error).join(". "),
			});
		} finally {
			setTestingId(null);
		}
	};

	return (
		<div>
			{showHeader && (
				<PageHeader
					title="Indexers"
					description="Private trackers and other sites Kinora searches directly, alongside the built-in indexers. New indexers are in the Open trust tier, so only profiles on the Open safety template download from them until the tier is changed."
					gradientFrom="teal-600/10"
					gradientVia="cyan-600/10"
					gradientTo="blue-600/10"
				/>
			)}
			<div className="p-8">
				<div className="max-w-6xl mx-auto space-y-6">
					{/* Controls */}
					<div className="flex items-center gap-4">
						<button
							type="button"
							onClick={() => setEditing("new")}
							disabled={!kinds}
							className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition cursor-pointer disabled:opacity-50"
						>
							<Plus className="w-4 h-4" />
							Add indexer
						</button>
					</div>

					{isLoading && (
						<div className="text-center py-8 text-muted-foreground">
							Loading indexers...
						</div>
					)}

					{!isLoading && (indexers || []).length === 0 && (
						<div className="text-center py-12 bg-card border border-border rounded-lg">
							<Server className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
							<p className="text-muted-foreground">
								No indexers added
							</p>
							<p className="text-sm text-muted-foreground mt-1">
								Add a UNIT3D, Gazelle or Torznab tracker, a
								passkey RSS feed, or any other site through a
								definition.
							</p>
						</div>
					)}

					<div className="space-y-4">
						{(indexers || []).map((indexer) => {
							const health =
								HEALTH[indexer.health.status] ||
								HEALTH.untested;
							const HealthIcon = health.icon;
							const tier = TRUST_TIERS.find(
								(t) => t.id === indexer.trust_tier,
							);
							const off =
								!indexer.enable_search && !indexer.enable_rss;
							return (
								<div
									key={indexer.id}
									className="bg-card text-card-foreground border-border border rounded-lg p-4 shadow-sm space-y-3"
								>
									<div
										className={`flex items-start justify-between gap-4 ${off ? "opacity-50" : ""}`}
									>
										<div className="min-w-0">
											<p className="text-sm font-semibold flex items-center gap-2">
												<span title={health.label}>
													<HealthIcon
														className={`w-4 h-4 ${health.color}`}
													/>
												</span>
												{indexer.name}
												{indexer.is_private && (
													<span title="Private tracker">
														<Lock className="w-3 h-3 text-muted-foreground" />
													</span>
												)}
											</p>
											<div className="flex flex-wrap gap-3 text-xs text-muted-foreground mt-1">
												<span className="px-2 py-0.5 bg-muted rounded">
													{indexer.kind_label}
												</span>
												<span
													className={`px-2 py-0.5 rounded ${TIER_COLORS[indexer.trust_tier] || "bg-muted"}`}
													title={tier?.description}
												>
													{tier?.name ||
														indexer.trust_tier}{" "}
													tier
												</span>
												<span className="break-all">
													{indexer.base_url}
												</span>
												<span>
													{SCOPES.filter((scope) =>
														indexer.media_types.includes(
															scope.id,
														),
													)
														.map(
															(scope) =>
																scope.name,
														)
														.join(", ")}
												</span>
												{indexer.min_ratio ||
												indexer.min_seed_minutes ? (
													<span>
														Seed to
														{indexer.min_ratio
															? ` ratio ${indexer.min_ratio}`
															: ""}
														{indexer.min_ratio &&
														indexer.min_seed_minutes
															? " and"
															: ""}
														{indexer.min_seed_minutes
															? ` ${Math.round((indexer.min_seed_minutes / 60) * 10) / 10} hours`
															: ""}
													</span>
												) : null}
											</div>
											{indexer.health.last_error &&
												indexer.health.failures > 0 && (
													<p className="text-xs text-red-500 mt-1 break-all">
														{
															indexer.health
																.failures
														}{" "}
														failed in a row.{" "}
														{
															indexer.health
																.last_error
														}
													</p>
												)}
											{indexer.last_test_at && (
												<p className="text-xs text-muted-foreground mt-1">
													Last test{" "}
													{new Date(
														indexer.last_test_at,
													).toLocaleString()}
													{indexer.last_test_ok
														? " passed"
														: ` failed. ${indexer.last_test_message || ""}`}
												</p>
											)}
										</div>
										<div className="flex items-center gap-3 flex-shrink-0">
											<div
												className="flex items-center gap-1 text-xs text-muted-foreground"
												title="Search"
											>
												<Search className="w-3.5 h-3.5" />
												<Toggle
													enabled={
														indexer.enable_search
													}
													onChange={(value) =>
														toggleMutation.mutate({
															indexer,
															toggles: {
																enable_search:
																	value,
															},
														})
													}
													title={
														indexer.enable_search
															? "Turn search off"
															: "Turn search on"
													}
												/>
											</div>
											<div
												className="flex items-center gap-1 text-xs text-muted-foreground"
												title="RSS"
											>
												<Rss className="w-3.5 h-3.5" />
												<Toggle
													enabled={indexer.enable_rss}
													disabled={
														!indexer.supports_rss
													}
													onChange={(value) =>
														toggleMutation.mutate({
															indexer,
															toggles: {
																enable_rss:
																	value,
															},
														})
													}
													title={
														indexer.supports_rss
															? indexer.enable_rss
																? "Turn RSS off"
																: "Turn RSS on"
															: "This type has no feed"
													}
												/>
											</div>
											<button
												type="button"
												onClick={() => runTest(indexer)}
												disabled={
													testingId === indexer.id
												}
												className="p-1.5 bg-muted rounded hover:bg-muted/80 transition cursor-pointer disabled:opacity-50"
												title="Test"
											>
												{testingId === indexer.id ? (
													<Loader2 className="w-3.5 h-3.5 animate-spin" />
												) : (
													<FlaskConical className="w-3.5 h-3.5" />
												)}
											</button>
											<button
												type="button"
												onClick={() =>
													setEditing(indexer)
												}
												disabled={!kinds}
												className="p-1.5 bg-muted rounded hover:bg-muted/80 transition cursor-pointer disabled:opacity-50"
												title="Edit"
											>
												<Pencil className="w-3.5 h-3.5" />
											</button>
											<button
												type="button"
												onClick={() =>
													setDeleting(indexer)
												}
												className="p-1.5 bg-muted rounded hover:bg-destructive/10 hover:text-destructive transition cursor-pointer"
												title="Delete"
											>
												<Trash2 className="w-3.5 h-3.5" />
											</button>
										</div>
									</div>
									{testResults[indexer.id] && (
										<IndexerTestPanel
											result={testResults[indexer.id]}
											onClose={() =>
												setTestResults((current) => {
													const next = { ...current };
													delete next[indexer.id];
													return next;
												})
											}
										/>
									)}
								</div>
							);
						})}
					</div>
				</div>

				{editing !== null && kinds && (
					<IndexerEditor
						indexer={editing === "new" ? null : editing}
						kinds={kinds}
						templates={templates || []}
						onClose={() => setEditing(null)}
						onSaved={(saved) => {
							toast.success("Indexer saved", {
								description: saved.name,
							});
							setEditing(null);
							refresh();
						}}
					/>
				)}

				<ConfirmModal
					isOpen={deleting !== null}
					title="Delete indexer"
					message={
						deleting
							? `Delete ${deleting.name}? Searches and RSS stop using it. Torrents already downloaded from it stay in qBittorrent, and its seeding minimum stays in the download client settings so they keep their protection.`
							: ""
					}
					confirmText={
						deleteMutation.isPending ? "Deleting" : "Delete"
					}
					variant="danger"
					onConfirm={() =>
						deleting && deleteMutation.mutate(deleting)
					}
					onCancel={() => setDeleting(null)}
				/>
			</div>
		</div>
	);
}
