"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, Loader2, RotateCcw } from "lucide-react";
import { api } from "@/lib/api";
import { useToast } from "@/components/toast/ToastProvider";
import { usePermissions } from "@/contexts/PermissionContext";

interface ImportFailedActionsProps {
	historyId: number;
	mediaType: string;
	mediaId: number;
	releaseTitle: string;
	// Off on the item's own page, where manual import is already shown.
	showItemLink?: boolean;
}

// Library page for each media type, where manual import is available.
const ITEM_ROUTES: Record<string, string> = {
	movie: "/movies",
	show: "/shows",
	anime: "/anime",
	album: "/music/album",
};

// Actions for a download whose files could not be imported. Retry import runs the import
// again, and Manual import opens the item to import files by hand.
export default function ImportFailedActions({
	historyId,
	mediaType,
	mediaId,
	releaseTitle,
	showItemLink = true,
}: ImportFailedActionsProps) {
	const queryClient = useQueryClient();
	const toast = useToast();
	const { hasPermission } = usePermissions();
	const [retried, setRetried] = useState(false);
	const canRetry = hasPermission("system.downloads");

	const mutation = useMutation({
		mutationFn: async () => {
			const res = await api.post(`/history/${historyId}/retry-import`);
			return res.data;
		},
		onSuccess: () => {
			setRetried(true);
			toast.success("Import started again", {
				description: releaseTitle,
			});
			queryClient.invalidateQueries({ queryKey: ["download-history"] });
			queryClient.invalidateQueries({ queryKey: ["history"] });
		},
		onError: (error: any) => {
			toast.error("Couldn't retry import", {
				description: error.response?.data?.detail || releaseTitle,
				actions: [{ label: "Retry", onClick: () => mutation.mutate() }],
			});
		},
	});

	const itemRoute = ITEM_ROUTES[mediaType];

	return (
		<div className="flex items-center gap-2">
			{canRetry && (
				<button
					onClick={() => mutation.mutate()}
					disabled={mutation.isPending || retried}
					className="flex items-center gap-1 px-2 py-1 text-xs rounded bg-primary text-primary-foreground hover:opacity-90 transition cursor-pointer disabled:opacity-50"
					title="Run the import again for this download"
				>
					{mutation.isPending ? (
						<Loader2 className="w-3.5 h-3.5 animate-spin" />
					) : (
						<RotateCcw className="w-3.5 h-3.5" />
					)}
					{retried ? "Import started" : "Retry import"}
				</button>
			)}
			{showItemLink && itemRoute && (
				<Link
					href={`${itemRoute}/${mediaId}`}
					className="flex items-center gap-1 px-2 py-1 text-xs rounded bg-muted hover:bg-muted/80 transition cursor-pointer"
					title="Open the item to import files by hand"
				>
					<ExternalLink className="w-3.5 h-3.5" />
					Manual import
				</Link>
			)}
		</div>
	);
}
