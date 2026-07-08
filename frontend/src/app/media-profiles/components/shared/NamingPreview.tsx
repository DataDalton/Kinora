"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface NamingPreviewProps {
	mediaType: "movie" | "show" | "anime" | "music";
	folderFormat?: string;
	namingFormat?: string;
}

interface PreviewResult {
	folder: string;
	file: string;
	unknown_tokens: string[];
}

export default function NamingPreview({
	mediaType,
	folderFormat,
	namingFormat,
}: NamingPreviewProps) {
	const [result, setResult] = useState<PreviewResult | null>(null);

	useEffect(() => {
		let active = true;
		const timer = setTimeout(async () => {
			try {
				const { data } = await api.post(
					"/media-profiles/naming-preview",
					{
						media_type: mediaType,
						folder_format: folderFormat,
						naming_format: namingFormat,
					},
				);
				if (active) setResult(data);
			} catch {
				if (active) setResult(null);
			}
		}, 300);
		return () => {
			active = false;
			clearTimeout(timer);
		};
	}, [mediaType, folderFormat, namingFormat]);

	if (!result || (!result.folder && !result.file)) return null;

	return (
		<div className="mt-2 p-3 rounded-lg bg-muted/40 border border-border text-xs">
			<div className="font-semibold text-muted-foreground mb-1">
				Preview
			</div>
			{result.folder && (
				<div className="font-mono break-all">
					<span className="text-muted-foreground">Folder: </span>
					{result.folder}
				</div>
			)}
			{result.file && (
				<div className="font-mono break-all">
					<span className="text-muted-foreground">File: </span>
					{result.file}
				</div>
			)}
			{result.unknown_tokens && result.unknown_tokens.length > 0 && (
				<div className="mt-1 text-amber-500">
					Unknown tokens: {result.unknown_tokens.join(", ")}
				</div>
			)}
		</div>
	);
}
