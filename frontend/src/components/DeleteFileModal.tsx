"use client";

import { AlertTriangle, Loader2, Trash2 } from "lucide-react";
import { useModalDismiss } from "@/hooks/useModalDismiss";

interface DeleteFileModalProps {
	fileName: string;
	directory: string;
	sizeLabel: string;
	// The item keeps its other versions, so the warning differs when none would remain.
	isLastFile: boolean;
	isLoading: boolean;
	onConfirm: () => void;
	onCancel: () => void;
}

// Confirms deleting one file version from disk. The library item stays either way.
export default function DeleteFileModal({
	fileName,
	directory,
	sizeLabel,
	isLastFile,
	isLoading,
	onConfirm,
	onCancel,
}: DeleteFileModalProps) {
	const backdropProps = useModalDismiss({
		onClose: onCancel,
		closeOnOutsideClick: true,
		disabled: isLoading,
	});

	return (
		<div
			className="fixed inset-0 backdrop-blur-sm bg-background/50 z-[60] flex items-center justify-center p-4"
			{...backdropProps}
		>
			<div
				role="dialog"
				aria-modal="true"
				aria-labelledby="delete-file-title"
				className="bg-background rounded-lg max-w-md w-full border border-border shadow-2xl p-6"
			>
				<div className="flex items-start gap-4 mb-4">
					<div className="p-2 rounded-full bg-destructive/20">
						<AlertTriangle className="w-6 h-6 text-destructive" />
					</div>
					<div className="flex-1 min-w-0">
						<h2
							id="delete-file-title"
							className="text-xl font-bold mb-2"
						>
							Delete File
						</h2>
						<p className="text-muted-foreground">
							This permanently deletes the file from disk. The
							item stays in your library.
						</p>
					</div>
				</div>

				<div className="bg-muted/50 rounded-lg p-4 mb-4 border border-border">
					<p className="font-medium text-foreground break-all">
						{fileName}
					</p>
					{directory && (
						<p className="text-xs text-muted-foreground mt-1 break-all">
							{directory}
						</p>
					)}
					<p className="text-xs text-muted-foreground mt-1">
						{sizeLabel}
					</p>
				</div>

				{isLastFile && (
					<div className="bg-destructive/10 border border-destructive/30 rounded-lg p-3 mb-4">
						<p className="text-sm text-destructive flex items-center gap-2">
							<AlertTriangle className="w-4 h-4 flex-shrink-0" />
							This is the only file, so the item will have no file
							left
						</p>
					</div>
				)}

				<div className="flex gap-3 justify-end pt-4">
					<button
						onClick={onCancel}
						disabled={isLoading}
						className="px-6 py-2 bg-muted text-foreground rounded-lg hover:opacity-90 cursor-pointer transition disabled:opacity-50"
					>
						Cancel
					</button>
					<button
						onClick={onConfirm}
						disabled={isLoading}
						className="px-6 py-2 rounded-lg hover:opacity-90 cursor-pointer transition bg-destructive text-destructive-foreground flex items-center gap-2 disabled:opacity-50"
					>
						{isLoading ? (
							<>
								<Loader2 className="w-4 h-4 animate-spin" />
								Deleting...
							</>
						) : (
							<>
								<Trash2 className="w-4 h-4" />
								Delete File
							</>
						)}
					</button>
				</div>
			</div>
		</div>
	);
}
