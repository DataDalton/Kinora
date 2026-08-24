"use client";

import { useState } from "react";
import { X } from "lucide-react";
import type { AddTorrentInput } from "../../../types/downloads";

interface AddTorrentModalProps {
	onClose: () => void;
	onSubmit: (input: AddTorrentInput) => Promise<void>;
}

export default function AddTorrentModal({
	onClose,
	onSubmit,
}: AddTorrentModalProps) {
	const [url, setUrl] = useState("");
	const [category, setCategory] = useState("");
	const [savePath, setSavePath] = useState("");
	const [submitting, setSubmitting] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const handleSubmit = async () => {
		if (!url.trim()) {
			setError("Enter a magnet link or .torrent URL");
			return;
		}
		setSubmitting(true);
		setError(null);
		try {
			await onSubmit({
				url: url.trim(),
				category: category.trim() || undefined,
				save_path: savePath.trim() || undefined,
			});
			onClose();
		} catch (err: unknown) {
			setError(
				err instanceof Error ? err.message : "Failed to add torrent",
			);
			setSubmitting(false);
		}
	};

	return (
		<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
			<div className="bg-card text-card-foreground rounded-lg shadow-xl w-full max-w-lg">
				<div className="flex items-center justify-between p-4 border-b border-border">
					<h2 className="text-lg font-semibold">Add Torrent</h2>
					<button
						onClick={onClose}
						className="p-1 rounded hover:bg-accent cursor-pointer"
					>
						<X className="w-5 h-5" />
					</button>
				</div>
				<div className="p-4 space-y-4">
					<div>
						<label className="block text-sm font-medium mb-1">
							Magnet link or .torrent URL
						</label>
						<textarea
							value={url}
							onChange={(e) => setUrl(e.target.value)}
							rows={3}
							placeholder="magnet:?xt=urn:btih:..."
							className="w-full px-3 py-2 rounded-lg bg-background border border-border focus:border-primary/50 focus:outline-none text-sm"
						/>
					</div>
					<div className="grid grid-cols-2 gap-3">
						<div>
							<label className="block text-sm font-medium mb-1">
								Category (optional)
							</label>
							<input
								value={category}
								onChange={(e) => setCategory(e.target.value)}
								placeholder="movies"
								className="w-full px-3 py-2 rounded-lg bg-background border border-border focus:border-primary/50 focus:outline-none text-sm"
							/>
						</div>
						<div>
							<label className="block text-sm font-medium mb-1">
								Save path (optional)
							</label>
							<input
								value={savePath}
								onChange={(e) => setSavePath(e.target.value)}
								placeholder="/downloads/movies"
								className="w-full px-3 py-2 rounded-lg bg-background border border-border focus:border-primary/50 focus:outline-none text-sm"
							/>
						</div>
					</div>
					{error && (
						<p className="text-sm text-destructive">{error}</p>
					)}
				</div>
				<div className="flex justify-end gap-2 p-4 border-t border-border">
					<button
						onClick={onClose}
						className="px-4 py-2 rounded-lg border border-border hover:bg-accent transition text-sm cursor-pointer"
					>
						Cancel
					</button>
					<button
						onClick={handleSubmit}
						disabled={submitting}
						className="px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:opacity-90 transition text-sm disabled:opacity-50 cursor-pointer"
					>
						{submitting ? "Adding..." : "Add Torrent"}
					</button>
				</div>
			</div>
		</div>
	);
}
