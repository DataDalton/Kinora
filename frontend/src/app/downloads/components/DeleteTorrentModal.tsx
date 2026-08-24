"use client";

import { useState } from "react";
import { AlertTriangle, X } from "lucide-react";

interface DeleteTorrentModalProps {
	torrentName: string;
	onClose: () => void;
	onConfirm: (deleteFiles: boolean) => Promise<void>;
}

export default function DeleteTorrentModal({
	torrentName,
	onClose,
	onConfirm,
}: DeleteTorrentModalProps) {
	const [deleteFiles, setDeleteFiles] = useState(false);
	const [submitting, setSubmitting] = useState(false);

	const handleConfirm = async () => {
		setSubmitting(true);
		try {
			await onConfirm(deleteFiles);
			onClose();
		} catch {
			setSubmitting(false);
		}
	};

	return (
		<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
			<div className="bg-card text-card-foreground rounded-lg shadow-xl w-full max-w-md">
				<div className="flex items-center justify-between p-4 border-b border-border">
					<h2 className="text-lg font-semibold flex items-center gap-2">
						<AlertTriangle className="w-5 h-5 text-destructive" />
						Remove Torrent
					</h2>
					<button
						onClick={onClose}
						className="p-1 rounded hover:bg-accent cursor-pointer"
					>
						<X className="w-5 h-5" />
					</button>
				</div>
				<div className="p-4 space-y-4">
					<p className="text-sm text-muted-foreground">
						Remove{" "}
						<span className="font-medium text-foreground">
							{torrentName}
						</span>{" "}
						from the download client?
					</p>
					<label className="flex items-center gap-2 text-sm cursor-pointer">
						<input
							type="checkbox"
							checked={deleteFiles}
							onChange={(e) => setDeleteFiles(e.target.checked)}
							className="w-4 h-4"
						/>
						Also delete downloaded files from disk
					</label>
					{deleteFiles && (
						<p className="text-xs text-destructive">
							Files already hardlinked into your library are
							retained. Only the download-folder copy is deleted.
						</p>
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
						onClick={handleConfirm}
						disabled={submitting}
						className="px-4 py-2 rounded-lg bg-destructive text-white hover:opacity-90 transition text-sm disabled:opacity-50 cursor-pointer"
					>
						{submitting ? "Removing..." : "Remove"}
					</button>
				</div>
			</div>
		</div>
	);
}
