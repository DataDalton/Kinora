"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
	ArrowRight,
	CheckCircle,
	Loader2,
	Plug,
	Plus,
	Save,
	Trash2,
	XCircle,
} from "lucide-react";
import { api } from "@/lib/api";
import PageHeader from "@/components/PageHeader";
import { useToast } from "@/components/toast/ToastProvider";
import { usePermissions } from "@/contexts/PermissionContext";

interface JellyfinPathMapping {
	kinora_path: string;
	jellyfin_path: string;
}

interface JellyfinLastUpdate {
	state: string;
	message: string | null;
	pathCount: number | null;
	timestamp: string | null;
}

interface JellyfinConfig {
	enabled: boolean;
	url: string;
	api_key_set: boolean;
	path_mappings: JellyfinPathMapping[];
	last_update: JellyfinLastUpdate | null;
}

interface JellyfinTestResult {
	success: boolean;
	message: string;
	serverName?: string | null;
	version?: string | null;
}

// Form values while editing. apiKey holds only a newly typed key, the stored key is never sent to the browser.
interface JellyfinDraft {
	enabled: boolean;
	url: string;
	apiKey: string;
	pathMappings: JellyfinPathMapping[];
}

const QUERY_KEY = ["jellyfin-config"];

const inputClass =
	"w-full px-3 py-2 rounded-lg bg-background border border-border focus:border-primary/50 focus:outline-none text-sm";

function draftFromConfig(config: JellyfinConfig | undefined): JellyfinDraft {
	return {
		enabled: config?.enabled ?? false,
		url: config?.url ?? "",
		apiKey: "",
		pathMappings: config?.path_mappings ?? [],
	};
}

// Settings for telling Jellyfin which library folders changed after Kinora imports,
// renames, or deletes files. Kinora's own sign-in never depends on Jellyfin.
export function JellyfinSection() {
	const { hasPermission } = usePermissions();
	const queryClient = useQueryClient();
	const toast = useToast();
	const isAdmin = hasPermission("system.admin");

	// Null until the form is edited, so the saved values show without copying them into state.
	const [draft, setDraft] = useState<JellyfinDraft | null>(null);
	const [testResult, setTestResult] = useState<JellyfinTestResult | null>(
		null,
	);

	const { data: config, isLoading } = useQuery({
		queryKey: QUERY_KEY,
		queryFn: async () => {
			const response = await api.get("/settings/jellyfin/config");
			return response.data as JellyfinConfig;
		},
		enabled: isAdmin,
	});

	const form = draft ?? draftFromConfig(config);
	const updateForm = (changes: Partial<JellyfinDraft>) =>
		setDraft({ ...form, ...changes });

	const saveMutation = useMutation({
		mutationFn: async (values: JellyfinDraft) => {
			const response = await api.put("/settings/jellyfin/config", {
				enabled: values.enabled,
				url: values.url,
				api_key: values.apiKey.trim() ? values.apiKey : null,
				path_mappings: values.pathMappings.filter(
					(mapping) =>
						mapping.kinora_path.trim() &&
						mapping.jellyfin_path.trim(),
				),
			});
			return response.data as JellyfinConfig;
		},
		onSuccess: (saved) => {
			queryClient.setQueryData(QUERY_KEY, saved);
			setDraft(null);
			toast.success("Jellyfin settings saved");
		},
		onError: (error: any) => {
			toast.error("Couldn't save Jellyfin settings", {
				description: error.response?.data?.detail,
			});
		},
	});

	const removeKeyMutation = useMutation({
		mutationFn: async () => {
			const response = await api.put("/settings/jellyfin/config", {
				enabled: false,
				url: form.url,
				api_key: "",
				path_mappings: form.pathMappings,
			});
			return response.data as JellyfinConfig;
		},
		onSuccess: (saved) => {
			queryClient.setQueryData(QUERY_KEY, saved);
			setDraft(null);
			toast.success("Jellyfin API key removed", {
				description:
					"Library updates are turned off until a new key is saved.",
			});
		},
		onError: (error: any) => {
			toast.error("Couldn't remove the API key", {
				description: error.response?.data?.detail,
			});
		},
	});

	const testMutation = useMutation({
		mutationFn: async () => {
			const response = await api.post("/settings/jellyfin/test", {
				url: form.url || null,
				api_key: form.apiKey.trim() ? form.apiKey : null,
			});
			return response.data as JellyfinTestResult;
		},
		onSuccess: (result) => setTestResult(result),
		onError: (error: any) =>
			setTestResult({
				success: false,
				message:
					error.response?.data?.detail ||
					"The connection test did not complete",
			}),
	});

	if (!isAdmin) return null;

	const updateMapping = (
		index: number,
		changes: Partial<JellyfinPathMapping>,
	) =>
		updateForm({
			pathMappings: form.pathMappings.map((mapping, i) =>
				i === index ? { ...mapping, ...changes } : mapping,
			),
		});

	const canTest =
		!!form.url.trim() && (!!form.apiKey.trim() || !!config?.api_key_set);
	const lastUpdate = config?.last_update;

	return (
		<div>
			<PageHeader
				title="Jellyfin"
				description="After Kinora imports, renames, or deletes files, it tells Jellyfin which folders changed so they show up without waiting for a scheduled library scan. Jellyfin is never used to sign in to Kinora."
				gradientFrom="purple-600/10"
				gradientVia="violet-600/10"
				gradientTo="blue-600/10"
			/>
			<div className="p-8">
				<div className="max-w-6xl mx-auto space-y-6">
					{isLoading ? (
						<div className="text-center py-8 text-muted-foreground">
							Loading Jellyfin settings...
						</div>
					) : (
						<>
							<div className="bg-card text-card-foreground border-border border rounded-lg p-4 shadow-sm space-y-4">
								<label className="flex items-center justify-between p-3 bg-muted/50 rounded-lg cursor-pointer">
									<div>
										<div className="font-semibold">
											Send library changes to Jellyfin
										</div>
										<div className="text-xs text-muted-foreground">
											{form.enabled
												? "Jellyfin rescans each changed folder shortly after Kinora writes to it"
												: "Jellyfin only finds new files on its own scheduled scans"}
										</div>
									</div>
									{/* The knob is positioned against this wrapper, so nothing else belongs inside it. */}
									<div className="relative inline-flex items-center">
										<input
											type="checkbox"
											checked={form.enabled}
											onChange={(e) =>
												updateForm({
													enabled: e.target.checked,
												})
											}
											className="sr-only peer"
										/>
										<div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary/20 dark:peer-focus:ring-primary/40 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-primary"></div>
									</div>
								</label>

								<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
									<div>
										<label className="block text-sm font-medium mb-1">
											Server URL
										</label>
										<input
											type="url"
											value={form.url}
											onChange={(e) =>
												updateForm({
													url: e.target.value,
												})
											}
											placeholder="http://jellyfin:8096"
											className={inputClass}
										/>
									</div>
									<div>
										<label className="block text-sm font-medium mb-1">
											API key
										</label>
										<input
											type="password"
											autoComplete="off"
											value={form.apiKey}
											onChange={(e) =>
												updateForm({
													apiKey: e.target.value,
												})
											}
											placeholder={
												config?.api_key_set
													? "Saved. Enter a new key to replace it"
													: "Created in Jellyfin under Dashboard, API Keys"
											}
											className={inputClass}
										/>
										{config?.api_key_set && (
											<button
												type="button"
												onClick={() =>
													removeKeyMutation.mutate()
												}
												disabled={
													removeKeyMutation.isPending
												}
												className="flex items-center gap-1 px-2 py-1 mt-2 text-xs rounded bg-muted hover:bg-muted/80 transition cursor-pointer disabled:opacity-50"
											>
												<Trash2 className="w-3.5 h-3.5" />
												Remove saved key
											</button>
										)}
									</div>
								</div>

								<div className="flex flex-wrap items-center gap-3">
									<button
										type="button"
										onClick={() => testMutation.mutate()}
										disabled={
											!canTest || testMutation.isPending
										}
										className="flex items-center gap-2 px-4 py-2 bg-muted rounded-lg hover:bg-muted/80 disabled:opacity-50 transition cursor-pointer"
									>
										{testMutation.isPending ? (
											<Loader2 className="w-4 h-4 animate-spin" />
										) : (
											<Plug className="w-4 h-4" />
										)}
										Test connection
									</button>
									{testResult && (
										<span
											className={`flex items-center gap-1 text-sm ${
												testResult.success
													? "text-green-500"
													: "text-destructive"
											}`}
										>
											{testResult.success ? (
												<CheckCircle className="w-4 h-4" />
											) : (
												<XCircle className="w-4 h-4" />
											)}
											{testResult.message}
										</span>
									)}
								</div>
							</div>

							<div className="bg-card text-card-foreground border-border border rounded-lg p-4 shadow-sm space-y-3">
								<div>
									<h3 className="font-semibold">
										Path mappings
									</h3>
									<p className="text-xs text-muted-foreground mt-1">
										Needed when Jellyfin mounts the library
										at a different path than Kinora, for
										example in another container. Each
										Kinora path prefix is replaced with the
										Jellyfin path prefix before the change
										is sent.
									</p>
								</div>

								{form.pathMappings.length === 0 && (
									<p className="text-sm text-muted-foreground">
										No mappings. Paths are sent to Jellyfin
										as Kinora sees them.
									</p>
								)}

								{form.pathMappings.map((mapping, index) => (
									<div
										key={index}
										className="flex items-center gap-2"
									>
										<input
											type="text"
											value={mapping.kinora_path}
											onChange={(e) =>
												updateMapping(index, {
													kinora_path: e.target.value,
												})
											}
											placeholder="Kinora path, e.g. /media/movies"
											className={`flex-1 font-mono ${inputClass}`}
										/>
										<ArrowRight className="w-4 h-4 text-muted-foreground" />
										<input
											type="text"
											value={mapping.jellyfin_path}
											onChange={(e) =>
												updateMapping(index, {
													jellyfin_path:
														e.target.value,
												})
											}
											placeholder="Jellyfin path, e.g. /data/movies"
											className={`flex-1 font-mono ${inputClass}`}
										/>
										<button
											type="button"
											onClick={() =>
												updateForm({
													pathMappings:
														form.pathMappings.filter(
															(_, i) =>
																i !== index,
														),
												})
											}
											className="p-1.5 bg-muted rounded hover:bg-muted/80 transition cursor-pointer"
											title="Remove mapping"
										>
											<Trash2 className="w-3.5 h-3.5" />
										</button>
									</div>
								))}

								<button
									type="button"
									onClick={() =>
										updateForm({
											pathMappings: [
												...form.pathMappings,
												{
													kinora_path: "",
													jellyfin_path: "",
												},
											],
										})
									}
									className="flex items-center gap-1 px-2 py-1 text-xs rounded bg-muted hover:bg-muted/80 transition cursor-pointer"
								>
									<Plus className="w-3.5 h-3.5" />
									Add mapping
								</button>
							</div>

							{lastUpdate && (
								<div
									className={`flex items-start gap-2 p-3 rounded-lg border text-sm ${
										lastUpdate.state === "error"
											? "bg-destructive/10 border-destructive/50"
											: "bg-green-500/10 border-green-500/20"
									}`}
								>
									{lastUpdate.state === "error" ? (
										<XCircle className="w-4 h-4 text-destructive" />
									) : (
										<CheckCircle className="w-4 h-4 text-green-500" />
									)}
									<div>
										<div className="font-medium">
											{lastUpdate.state === "error"
												? "Last library update failed"
												: "Last library update delivered"}
										</div>
										<div className="text-xs text-muted-foreground">
											{lastUpdate.message}
											{lastUpdate.timestamp &&
												` (${new Date(lastUpdate.timestamp).toLocaleString()})`}
										</div>
									</div>
								</div>
							)}

							<div className="flex items-center gap-3">
								<button
									type="button"
									onClick={() => saveMutation.mutate(form)}
									disabled={!draft || saveMutation.isPending}
									className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 transition cursor-pointer"
								>
									{saveMutation.isPending ? (
										<Loader2 className="w-4 h-4 animate-spin" />
									) : (
										<Save className="w-4 h-4" />
									)}
									Save
								</button>
								{draft && (
									<button
										type="button"
										onClick={() => {
											setDraft(null);
											setTestResult(null);
										}}
										className="px-4 py-2 bg-muted rounded-lg hover:bg-muted/80 transition cursor-pointer"
									>
										Discard changes
									</button>
								)}
							</div>
						</>
					)}
				</div>
			</div>
		</div>
	);
}

export default JellyfinSection;
