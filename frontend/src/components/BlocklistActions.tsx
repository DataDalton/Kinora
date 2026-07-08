"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Ban, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import Toast from "./Toast";

interface BlocklistActionsProps {
	mediaType: string;
	mediaId: number;
	releaseTitle: string;
}

// Blocklist scopes that map cleanly to a single library item id.
const SUPPORTED = ["movie", "show", "anime", "album"];

// Two actions for a failed download: blocklist the release so automated search skips it,
// or blocklist and immediately search for a replacement. Used in the activity feed and the
// per-item download history.
export default function BlocklistActions({
	mediaType,
	mediaId,
	releaseTitle,
}: BlocklistActionsProps) {
	const queryClient = useQueryClient();
	const [toast, setToast] = useState<{
		message: string;
		type: "success" | "error" | "info";
	} | null>(null);
	const [done, setDone] = useState(false);

	const mutation = useMutation({
		mutationFn: async (searchAgain: boolean) => {
			const res = await api.post("/blocklist/release", {
				media_type: mediaType,
				media_id: mediaId,
				release_title: releaseTitle,
				search_again: searchAgain,
			});
			return res.data;
		},
		onSuccess: (data) => {
			setDone(true);
			setToast({
				message: data?.search_dispatched
					? "Blocklisted. Searching for a replacement..."
					: "Release blocklisted",
				type: "success",
			});
			queryClient.invalidateQueries({ queryKey: ["blocklist"] });
			queryClient.invalidateQueries({ queryKey: ["download-history"] });
			queryClient.invalidateQueries({ queryKey: ["history"] });
		},
		onError: (error: any) => {
			setToast({
				message: error.response?.data?.detail || "Failed to blocklist",
				type: "error",
			});
		},
	});

	if (!SUPPORTED.includes(mediaType)) return null;

	if (done) {
		return (
			<>
				<span className="flex items-center gap-1 text-xs text-muted-foreground">
					<Ban className="w-3.5 h-3.5" /> Blocklisted
				</span>
				{toast && (
					<Toast
						message={toast.message}
						type={toast.type}
						onClose={() => setToast(null)}
					/>
				)}
			</>
		);
	}

	return (
		<>
			<div className="flex items-center gap-2">
				<button
					onClick={() => mutation.mutate(false)}
					disabled={mutation.isPending}
					className="flex items-center gap-1 px-2 py-1 text-xs rounded bg-muted hover:bg-muted/80 transition cursor-pointer disabled:opacity-50"
					title="Blocklist this release so automated search skips it"
				>
					{mutation.isPending ? (
						<Loader2 className="w-3.5 h-3.5 animate-spin" />
					) : (
						<Ban className="w-3.5 h-3.5" />
					)}
					Blocklist
				</button>
				<button
					onClick={() => mutation.mutate(true)}
					disabled={mutation.isPending}
					className="flex items-center gap-1 px-2 py-1 text-xs rounded bg-primary text-primary-foreground hover:opacity-90 transition cursor-pointer disabled:opacity-50"
					title="Blocklist this release and search for a replacement now"
				>
					<Ban className="w-3.5 h-3.5" />
					Blocklist &amp; search
				</button>
			</div>
			{toast && (
				<Toast
					message={toast.message}
					type={toast.type}
					onClose={() => setToast(null)}
				/>
			)}
		</>
	);
}
