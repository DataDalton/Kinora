"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
	Lock,
	Pencil,
	Plus,
	RotateCcw,
	ShieldCheck,
	Trash2,
	Users,
	X,
} from "lucide-react";
import { api } from "@/lib/api";
import PageHeader from "@/components/PageHeader";
import ConfirmModal from "@/components/ConfirmModal";
import { useToast } from "@/components/toast/ToastProvider";

interface TrustedUploader {
	id: number;
	display_name: string;
	ext_name: string | null;
	leetx_name: string | null;
	is_default: boolean;
	enabled: boolean;
}

interface EntryDraft {
	display_name: string;
	ext_name: string;
	leetx_name: string;
	enabled: boolean;
}

const EMPTY_DRAFT: EntryDraft = {
	display_name: "",
	ext_name: "",
	leetx_name: "",
	enabled: true,
};

// Categories trusted without a list entry. They come from the sites themselves, so they
// cannot be edited here.
const FIXED_CATEGORIES = [
	{
		name: "ext.to verified",
		description: "Accounts with ext.to's Trusted Uploader badge",
	},
	{
		name: "Nyaa trusted",
		description: "Uploads Nyaa's staff mark trusted (green rows)",
	},
];

// The Kinora trusted list. Each entry holds the name ext.to shows for a verified account
// and the name 1337x shows, since one uploader can use a different name on each site.
export default function TrustedUploadersSection() {
	const queryClient = useQueryClient();
	const toast = useToast();
	const [editingId, setEditingId] = useState<number | "new" | null>(null);
	const [draft, setDraft] = useState<EntryDraft>(EMPTY_DRAFT);
	const [pendingDelete, setPendingDelete] = useState<TrustedUploader | null>(
		null,
	);

	const { data: entries } = useQuery({
		queryKey: ["trusted-uploaders"],
		queryFn: async () => {
			const response = await api.get("/trusted-uploaders/");
			return response.data as TrustedUploader[];
		},
	});

	const refresh = () =>
		queryClient.invalidateQueries({ queryKey: ["trusted-uploaders"] });
	const onError = (title: string) => (error: any) =>
		toast.error(title, { description: error.response?.data?.detail });

	const saveMutation = useMutation({
		mutationFn: async () => {
			if (editingId === "new") {
				await api.post("/trusted-uploaders/", draft);
			} else if (editingId !== null) {
				await api.put(`/trusted-uploaders/${editingId}`, draft);
			}
		},
		onSuccess: () => {
			toast.success("Trusted list saved", {
				description: draft.display_name,
			});
			setEditingId(null);
			refresh();
		},
		onError: onError("Couldn't save the entry"),
	});

	const toggleMutation = useMutation({
		mutationFn: async (entry: TrustedUploader) =>
			api.put(`/trusted-uploaders/${entry.id}`, {
				display_name: entry.display_name,
				ext_name: entry.ext_name,
				leetx_name: entry.leetx_name,
				enabled: !entry.enabled,
			}),
		onSuccess: refresh,
		onError: onError("Couldn't change the entry"),
	});

	const deleteMutation = useMutation({
		mutationFn: async (entry: TrustedUploader) =>
			api.delete(`/trusted-uploaders/${entry.id}`),
		onSuccess: refresh,
		onError: onError("Couldn't delete the entry"),
	});

	const restoreMutation = useMutation({
		mutationFn: async () => api.post("/trusted-uploaders/restore-defaults"),
		onSuccess: () => {
			toast.success("Default entries restored");
			refresh();
		},
		onError: onError("Couldn't restore the defaults"),
	});

	const startEdit = (entry: TrustedUploader | null) => {
		setEditingId(entry ? entry.id : "new");
		setDraft(
			entry
				? {
						display_name: entry.display_name,
						ext_name: entry.ext_name || "",
						leetx_name: entry.leetx_name || "",
						enabled: entry.enabled,
					}
				: EMPTY_DRAFT,
		);
	};

	const editor = (
		<div className="p-4 rounded-lg border border-border bg-muted/20 space-y-3">
			<div className="grid grid-cols-1 md:grid-cols-3 gap-3">
				{(
					[
						["display_name", "Name"],
						["ext_name", "Name on ext.to"],
						["leetx_name", "Name on 1337x"],
					] as const
				).map(([field, label]) => (
					<div key={field}>
						<label className="block text-sm font-medium mb-1">
							{label}
						</label>
						<input
							type="text"
							value={draft[field]}
							onChange={(e) =>
								setDraft({ ...draft, [field]: e.target.value })
							}
							className="w-full px-3 py-2 border-input bg-background text-foreground border rounded-lg text-sm"
						/>
					</div>
				))}
			</div>
			<p className="text-xs text-muted-foreground">
				Names are matched exactly, ignoring case. The ext.to name only
				counts on listings with ext.to&apos;s Trusted Uploader badge.
			</p>
			<div className="flex gap-2">
				<button
					type="button"
					onClick={() => saveMutation.mutate()}
					disabled={
						saveMutation.isPending || !draft.display_name.trim()
					}
					className="px-3 py-1.5 text-sm rounded bg-primary text-primary-foreground hover:opacity-90 transition cursor-pointer disabled:opacity-50"
				>
					Save
				</button>
				<button
					type="button"
					onClick={() => setEditingId(null)}
					className="flex items-center gap-1 px-3 py-1.5 text-sm rounded bg-muted hover:bg-muted/80 transition cursor-pointer"
				>
					<X className="w-3.5 h-3.5" />
					Cancel
				</button>
			</div>
		</div>
	);

	return (
		<div>
			<PageHeader
				title="Trusted Uploaders"
				description="Uploaders profiles on the Trusted or Balanced safety template accept. Changes apply to searches within a few minutes."
				gradientFrom="emerald-600/10"
				gradientVia="green-600/10"
				gradientTo="teal-600/10"
			/>

			<div className="p-8">
				<div className="max-w-6xl mx-auto space-y-6">
					{/* Controls */}
					<div className="flex items-center gap-4">
						<button
							type="button"
							onClick={() => startEdit(null)}
							className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition cursor-pointer"
						>
							<Plus className="w-4 h-4" />
							Add uploader
						</button>
						<button
							type="button"
							onClick={() => restoreMutation.mutate()}
							disabled={restoreMutation.isPending}
							className="flex items-center gap-2 px-4 py-2 bg-muted text-muted-foreground rounded-lg hover:bg-muted/80 transition cursor-pointer disabled:opacity-50"
						>
							<RotateCcw className="w-4 h-4" />
							Restore defaults
						</button>
					</div>

					<div>
						<h2 className="text-xl font-bold mb-4 flex items-center gap-2">
							<ShieldCheck className="w-5 h-5" />
							Always Trusted
						</h2>
						<div className="space-y-4">
							{FIXED_CATEGORIES.map((category) => (
								<div
									key={category.name}
									className="bg-card text-card-foreground border-border border rounded-lg p-4 shadow-sm flex items-center justify-between"
								>
									<div>
										<p className="text-sm font-semibold flex items-center gap-2">
											<ShieldCheck className="w-4 h-4 text-green-500" />
											{category.name}
										</p>
										<p className="text-xs text-muted-foreground">
											{category.description}
										</p>
									</div>
									<span className="flex items-center gap-1 text-xs text-muted-foreground">
										<Lock className="w-3 h-3" />
										Always trusted
									</span>
								</div>
							))}
						</div>
					</div>

					<div>
						<h2 className="text-xl font-bold mb-4 flex items-center gap-2">
							<Users className="w-5 h-5" />
							Kinora Trusted List
						</h2>
						<div className="space-y-4">
							{editingId === "new" && editor}
							{(entries || []).map((entry) =>
								editingId === entry.id ? (
									<div key={entry.id}>{editor}</div>
								) : (
									<div
										key={entry.id}
										className={`bg-card text-card-foreground border-border border rounded-lg p-4 shadow-sm flex items-center justify-between gap-2 ${
											entry.enabled ? "" : "opacity-50"
										}`}
									>
										<button
											type="button"
											role="switch"
											aria-checked={entry.enabled}
											onClick={() =>
												toggleMutation.mutate(entry)
											}
											className="flex-1 min-w-0 flex items-center justify-between gap-4 text-left cursor-pointer"
											title={
												entry.enabled
													? "Turn off"
													: "Turn on"
											}
										>
											<div className="min-w-0">
												<p className="text-sm font-semibold">
													{entry.display_name}
												</p>
												<div className="flex flex-wrap gap-3 text-xs text-muted-foreground mt-1">
													<span>
														ext.to{" "}
														{entry.ext_name ||
															"none"}
													</span>
													<span>
														1337x{" "}
														{entry.leetx_name ||
															"none"}
													</span>
													<span className="px-2 py-0.5 bg-muted rounded">
														{entry.is_default
															? "Default"
															: "Added"}
													</span>
												</div>
											</div>
											<span
												className={`relative inline-flex h-6 w-11 flex-shrink-0 items-center rounded-full transition-colors ${
													entry.enabled
														? "bg-primary"
														: "bg-muted"
												}`}
											>
												<span
													className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
														entry.enabled
															? "translate-x-6"
															: "translate-x-1"
													}`}
												/>
											</span>
										</button>
										<div className="flex items-center gap-2">
											<button
												type="button"
												onClick={() => startEdit(entry)}
												className="p-1.5 bg-muted rounded hover:bg-muted/80 transition cursor-pointer"
												title="Edit"
											>
												<Pencil className="w-3.5 h-3.5" />
											</button>
											{!entry.is_default && (
												<button
													type="button"
													onClick={() =>
														setPendingDelete(entry)
													}
													className="p-1.5 bg-muted rounded hover:bg-destructive/10 hover:text-destructive transition cursor-pointer"
													title="Delete"
												>
													<Trash2 className="w-3.5 h-3.5" />
												</button>
											)}
										</div>
									</div>
								),
							)}
						</div>
					</div>
				</div>
			</div>

			<ConfirmModal
				isOpen={pendingDelete !== null}
				title="Delete trusted uploader"
				message={`Releases from ${pendingDelete?.display_name} will no longer count as trusted, so Trusted profiles stop downloading them.`}
				confirmText="Delete"
				variant="danger"
				onConfirm={() => {
					if (pendingDelete) {
						deleteMutation.mutate(pendingDelete);
					}
					setPendingDelete(null);
				}}
				onCancel={() => setPendingDelete(null)}
			/>
		</div>
	);
}
