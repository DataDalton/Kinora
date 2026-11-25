"use client";

import { useMemo, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useVirtualizer } from "@tanstack/react-virtual";
import {
	ArrowRight,
	CircleAlert,
	CircleCheck,
	FilePen,
	Minus,
	X,
} from "lucide-react";
import { api } from "@/lib/api";
import { useModalDismiss } from "@/hooks/useModalDismiss";
import { useToast } from "@/components/toast/ToastProvider";

export type RenameStatus =
	| "change"
	| "unchanged"
	| "conflict"
	| "error"
	| "applied"
	| "stale";

export interface RenamePreviewEntry {
	mediaType: string;
	itemId: number;
	itemTitle: string | null;
	oldPath: string | null;
	newPath: string | null;
	status: RenameStatus;
	message: string | null;
}

interface RenamePreviewResponse {
	entries: RenamePreviewEntry[];
	counts: {
		change: number;
		unchanged: number;
		conflict: number;
		error: number;
	};
	total: number;
}

export interface RenameApplyResult {
	success: boolean;
	processed: number;
	failed: number;
	total: number;
	errors: string[];
	applied: number;
	stale: number;
	conflict: number;
	entries: RenamePreviewEntry[];
}

// The preview call and the apply call for one set of items. The apply call receives
// the previewed change entries and moves only those.
export interface RenamePreviewScope {
	previewEndpoint: string;
	previewBody?: Record<string, unknown>;
	applyEndpoint: string;
}

interface RenamePreviewModalProps {
	isOpen: boolean;
	title?: string;
	description?: string;
	scope: RenamePreviewScope | null;
	onClose: () => void;
	onApplied?: (result: RenameApplyResult) => void;
}

type RenameFilter = "all" | "change" | "conflict" | "error";

const FILTERS: { id: RenameFilter; label: string }[] = [
	{ id: "all", label: "All" },
	{ id: "change", label: "Changes" },
	{ id: "conflict", label: "Conflicts" },
	{ id: "error", label: "Errors" },
];

const STATUS_STYLES: Record<
	RenameStatus,
	{ label: string; className: string }
> = {
	change: { label: "Change", className: "bg-primary/20 text-primary" },
	unchanged: {
		label: "Unchanged",
		className: "bg-muted text-muted-foreground",
	},
	conflict: {
		label: "Conflict",
		className: "bg-yellow-500/20 text-yellow-500",
	},
	error: { label: "Error", className: "bg-destructive/20 text-destructive" },
	applied: { label: "Renamed", className: "bg-green-500/20 text-green-500" },
	stale: { label: "Stale", className: "bg-yellow-500/20 text-yellow-500" },
};

interface PathPart {
	text: string;
	changed: boolean;
}

// Splits both paths into folder segments and marks the segments between the shared
// leading and shared trailing segments as changed.
function diffPaths(
	oldPath: string,
	newPath: string,
): { oldParts: PathPart[]; newParts: PathPart[]; separator: string } {
	const separator = oldPath.includes("\\") ? "\\" : "/";
	const oldSegments = oldPath.split(/[\\/]/);
	const newSegments = newPath.split(/[\\/]/);
	let prefix = 0;
	while (
		prefix < oldSegments.length &&
		prefix < newSegments.length &&
		oldSegments[prefix] === newSegments[prefix]
	) {
		prefix += 1;
	}
	let suffix = 0;
	while (
		suffix < oldSegments.length - prefix &&
		suffix < newSegments.length - prefix &&
		oldSegments[oldSegments.length - 1 - suffix] ===
			newSegments[newSegments.length - 1 - suffix]
	) {
		suffix += 1;
	}
	const mark = (segments: string[]): PathPart[] =>
		segments.map((text, index) => ({
			text,
			changed: index >= prefix && index < segments.length - suffix,
		}));
	return {
		oldParts: mark(oldSegments),
		newParts: mark(newSegments),
		separator,
	};
}

function PathView({
	parts,
	separator,
	highlightClass,
}: {
	parts: PathPart[];
	separator: string;
	highlightClass: string;
}) {
	return (
		<p className="text-xs font-mono break-all">
			{parts.map((part, index) => (
				<span key={index}>
					{index > 0 && (
						<span className="text-muted-foreground">
							{separator}
						</span>
					)}
					<span
						className={
							part.changed
								? `${highlightClass} rounded px-1`
								: "text-muted-foreground"
						}
					>
						{part.text}
					</span>
				</span>
			))}
		</p>
	);
}

function EntryRow({ entry }: { entry: RenamePreviewEntry }) {
	const style = STATUS_STYLES[entry.status] ?? STATUS_STYLES.error;
	const paths =
		entry.oldPath && entry.newPath
			? diffPaths(entry.oldPath, entry.newPath)
			: null;
	const showNew = entry.status !== "unchanged";

	return (
		<div className="px-4 py-2 border-b border-border">
			<div className="flex items-center gap-2 mb-1">
				<span
					className={`px-2 py-0.5 rounded-full text-xs font-medium ${style.className}`}
				>
					{style.label}
				</span>
				<span className="text-sm font-medium truncate">
					{entry.itemTitle || `${entry.mediaType} ${entry.itemId}`}
				</span>
				<span className="text-xs text-muted-foreground uppercase">
					{entry.mediaType}
				</span>
			</div>
			<div className="grid md:grid-cols-2 gap-2">
				<div className="min-w-0">
					{paths ? (
						<PathView
							parts={paths.oldParts}
							separator={paths.separator}
							highlightClass={
								showNew
									? "bg-destructive/20 text-destructive"
									: "text-foreground"
							}
						/>
					) : (
						<p className="text-xs font-mono break-all text-muted-foreground">
							{entry.oldPath || "No file path"}
						</p>
					)}
				</div>
				<div className="min-w-0 flex items-start gap-2">
					<ArrowRight className="w-3 h-3 mt-1 text-muted-foreground shrink-0" />
					{paths && showNew ? (
						<PathView
							parts={paths.newParts}
							separator={paths.separator}
							highlightClass="bg-green-500/20 text-green-500"
						/>
					) : (
						<p className="text-xs text-muted-foreground">
							{entry.status === "unchanged"
								? "Already named correctly"
								: "No new path"}
						</p>
					)}
				</div>
			</div>
			{entry.message && (
				<p
					className={`text-xs mt-1 ${entry.status === "error" ? "text-destructive" : "text-yellow-500"}`}
				>
					{entry.message}
				</p>
			)}
		</div>
	);
}

/**
 * Shows every file a rename would move, side by side with its new path, and applies
 * only the previewed change entries on confirm. Nothing on disk changes until confirm.
 */
export default function RenamePreviewModal({
	isOpen,
	title = "Preview Rename",
	description,
	scope,
	onClose,
	onApplied,
}: RenamePreviewModalProps) {
	const toast = useToast();
	const [filter, setFilter] = useState<RenameFilter>("all");
	const listRef = useRef<HTMLDivElement>(null);

	const previewQuery = useQuery({
		queryKey: [
			"rename-preview",
			scope?.previewEndpoint,
			JSON.stringify(scope?.previewBody ?? {}),
		],
		queryFn: async () => {
			const response = await api.post(
				scope!.previewEndpoint,
				scope!.previewBody ?? {},
			);
			return response.data as RenamePreviewResponse;
		},
		enabled: isOpen && !!scope,
		staleTime: 0,
		gcTime: 0,
		refetchOnWindowFocus: false,
	});

	const preview = previewQuery.data;
	const changeEntries = useMemo(
		() => (preview?.entries ?? []).filter((e) => e.status === "change"),
		[preview],
	);
	const visibleEntries = useMemo(() => {
		const entries = preview?.entries ?? [];
		return filter === "all"
			? entries
			: entries.filter((e) => e.status === filter);
	}, [preview, filter]);

	const applyMutation = useMutation({
		mutationFn: async () => {
			const response = await api.post(scope!.applyEndpoint, {
				entries: changeEntries.map((e) => ({
					mediaType: e.mediaType,
					itemId: e.itemId,
					oldPath: e.oldPath,
					newPath: e.newPath,
				})),
			});
			return response.data as RenameApplyResult;
		},
		onSuccess: (result) => {
			const skipped = result.stale + result.conflict + result.failed;
			const parts = [`${result.applied} renamed`];
			if (result.stale) parts.push(`${result.stale} stale`);
			if (result.conflict) parts.push(`${result.conflict} conflicts`);
			if (result.failed) parts.push(`${result.failed} failed`);
			if (skipped === 0) {
				toast.success("Files renamed", {
					description: parts.join(", "),
				});
			} else {
				toast.warning("Some files were not renamed", {
					description: `${parts.join(", ")}. Preview again to review the skipped files.`,
				});
			}
			onApplied?.(result);
			onClose();
		},
		onError: (error: Error) => {
			toast.error("Couldn't rename files", {
				description: error.message,
			});
		},
	});

	const backdropProps = useModalDismiss({
		onClose,
		isOpen,
		closeOnOutsideClick: true,
		disabled: applyMutation.isPending,
	});

	const virtualizer = useVirtualizer({
		count: visibleEntries.length,
		getScrollElement: () => listRef.current,
		estimateSize: () => 88,
		overscan: 8,
	});

	if (!isOpen || !scope) return null;

	const counts = preview?.counts;
	const filterCount = (id: RenameFilter) =>
		id === "all" ? (preview?.total ?? 0) : (counts?.[id] ?? 0);

	return (
		<div className="fixed inset-0 z-50 flex items-center justify-center">
			<div
				className="absolute inset-0 bg-black/60 backdrop-blur-sm"
				{...backdropProps}
			/>
			<div className="relative bg-background rounded-xl border border-border shadow-2xl w-full max-w-6xl mx-4 flex flex-col max-h-[90vh]">
				<div className="flex items-start justify-between gap-4 p-6 border-b border-border">
					<div className="flex items-center gap-3">
						<div className="p-2 bg-primary/20 rounded-lg">
							<FilePen className="w-6 h-6 text-primary" />
						</div>
						<div>
							<h3 className="text-lg font-semibold">{title}</h3>
							<p className="text-sm text-muted-foreground">
								{description ||
									"Nothing is moved until the rename is confirmed."}
							</p>
						</div>
					</div>
					<button
						onClick={onClose}
						disabled={applyMutation.isPending}
						className="p-1.5 hover:bg-muted rounded-lg transition cursor-pointer"
						title="Close"
						aria-label="Close"
					>
						<X className="w-4 h-4" />
					</button>
				</div>

				{counts && (
					<div className="flex flex-wrap items-center gap-2 px-6 py-4 border-b border-border">
						<span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs bg-primary/20 text-primary">
							<FilePen className="w-3 h-3" />
							{counts.change} to rename
						</span>
						<span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs bg-muted text-muted-foreground">
							<Minus className="w-3 h-3" />
							{counts.unchanged} unchanged
						</span>
						<span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs bg-yellow-500/20 text-yellow-500">
							<CircleAlert className="w-3 h-3" />
							{counts.conflict} conflicts
						</span>
						<span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs bg-destructive/20 text-destructive">
							<CircleAlert className="w-3 h-3" />
							{counts.error} errors
						</span>
						<div className="flex items-center gap-1 ml-auto">
							{FILTERS.map((option) => (
								<button
									key={option.id}
									onClick={() => {
										setFilter(option.id);
										listRef.current?.scrollTo({ top: 0 });
									}}
									className={`px-3 py-1.5 rounded-lg transition text-sm cursor-pointer ${
										filter === option.id
											? "bg-primary text-primary-foreground"
											: "bg-muted hover:bg-muted/80"
									}`}
								>
									{option.label} ({filterCount(option.id)})
								</button>
							))}
						</div>
					</div>
				)}

				<div
					ref={listRef}
					className="overflow-y-auto"
					style={{ height: "55vh" }}
				>
					{previewQuery.isLoading && (
						<div className="flex flex-col items-center justify-center h-full gap-3 text-muted-foreground">
							<div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
							<p className="text-sm">
								Working out the new file names...
							</p>
						</div>
					)}
					{previewQuery.isError && (
						<div className="flex flex-col items-center justify-center h-full gap-2 text-destructive">
							<CircleAlert className="w-8 h-8" />
							<p className="text-sm">
								{(previewQuery.error as Error).message ||
									"Couldn't build the rename preview"}
							</p>
						</div>
					)}
					{preview && visibleEntries.length === 0 && (
						<div className="flex flex-col items-center justify-center h-full gap-2 text-muted-foreground">
							<CircleCheck className="w-8 h-8" />
							<p className="text-sm">
								{preview.total === 0
									? "No files to rename"
									: "No files match this filter"}
							</p>
						</div>
					)}
					{preview && visibleEntries.length > 0 && (
						<div
							style={{
								height: `${virtualizer.getTotalSize()}px`,
								width: "100%",
								position: "relative",
							}}
						>
							{virtualizer.getVirtualItems().map((virtualRow) => (
								<div
									key={virtualRow.key}
									data-index={virtualRow.index}
									ref={virtualizer.measureElement}
									style={{
										position: "absolute",
										top: 0,
										left: 0,
										width: "100%",
										transform: `translateY(${virtualRow.start}px)`,
									}}
								>
									<EntryRow
										entry={visibleEntries[virtualRow.index]}
									/>
								</div>
							))}
						</div>
					)}
				</div>

				<div className="flex items-center justify-between gap-3 p-6 border-t border-border">
					<p className="text-xs text-muted-foreground">
						Conflicts and errors are skipped. Files whose new path
						changes before confirming are reported as stale and left
						in place.
					</p>
					<div className="flex gap-3 shrink-0">
						<button
							onClick={onClose}
							disabled={applyMutation.isPending}
							className="px-4 py-2 text-sm font-medium hover:bg-muted rounded-lg transition cursor-pointer"
						>
							Cancel
						</button>
						<button
							onClick={() => applyMutation.mutate()}
							disabled={
								changeEntries.length === 0 ||
								applyMutation.isPending ||
								previewQuery.isFetching
							}
							className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground text-sm font-medium rounded-lg hover:bg-primary/90 transition cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
						>
							{applyMutation.isPending && (
								<div className="w-4 h-4 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin" />
							)}
							Rename {changeEntries.length}{" "}
							{changeEntries.length === 1 ? "file" : "files"}
						</button>
					</div>
				</div>
			</div>
		</div>
	);
}
