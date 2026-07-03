"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { SectionProps } from "../types";
import { SHOW_PRESETS } from "../constants";

const SHOW_TOKENS = [
	{
		token: "{Show Title}",
		description: "Show title",
		example: "Breaking Bad",
	},
	{
		token: "{Show CleanTitle}",
		description: "Clean title without special chars",
		example: "Breaking Bad",
	},
	{
		token: "{Show TitleThe}",
		description: 'Title with "The" at end',
		example: "Walking Dead, The",
	},
	{
		token: "{Release Year}",
		description: "Show release year",
		example: "2008",
	},
	{ token: "{TvdbId}", description: "TVDB database ID", example: "81189" },
	{ token: "{TmdbId}", description: "TMDB database ID", example: "1396" },
	{
		token: "{ImdbId}",
		description: "IMDB database ID",
		example: "tt0903747",
	},
	{ token: "{Season}", description: "Season number", example: "01" },
	{
		token: "{Season:00}",
		description: "Season number (2 digits)",
		example: "01",
	},
	{ token: "{Episode}", description: "Episode number", example: "05" },
	{
		token: "{Episode:00}",
		description: "Episode number (2 digits)",
		example: "05",
	},
	{
		token: "{Episode Title}",
		description: "Episode title",
		example: "Pilot",
	},
	{
		token: "{Absolute Episode}",
		description: "Absolute episode number",
		example: "52",
	},
	{ token: "{Air Date}", description: "Air date", example: "2008-01-20" },
	{
		token: "{Quality Full}",
		description: "Full quality string",
		example: "HDTV-720p",
	},
	{
		token: "{Quality Resolution}",
		description: "Resolution",
		example: "720p",
	},
	{
		token: "{MediaInfo VideoCodec}",
		description: "Video codec",
		example: "x264",
	},
	{
		token: "{MediaInfo AudioCodec}",
		description: "Audio codec",
		example: "AAC",
	},
	{
		token: "{MediaInfo AudioChannels}",
		description: "Audio channels",
		example: "2.0",
	},
	{
		token: "{Release Group}",
		description: "Release group name",
		example: "LOL",
	},
];

export default function TVShows({ formData, setFormData }: SectionProps) {
	const [showBuilder, setShowBuilder] = useState(false);
	const [activeField, setActiveField] = useState<"folder" | "file">("file");

	const insertToken = (token: string) => {
		if (activeField === "folder") {
			setFormData({
				...formData,
				show_folder_format: formData.show_folder_format + token,
			});
		} else {
			setFormData({
				...formData,
				show_naming_format: formData.show_naming_format + token,
			});
		}
	};

	const applyPreset = (preset: (typeof SHOW_PRESETS)[0]) => {
		setFormData({
			...formData,
			show_folder_format: preset.folder,
			show_naming_format: preset.file,
		});
	};

	return (
		<div className="space-y-4">
			{/* Show Folder Format */}
			<div>
				<div className="flex justify-between items-center mb-2">
					<label className="block text-sm font-semibold">
						Show Folder Format
					</label>
					<button
						type="button"
						onClick={() => {
							setActiveField("folder");
							setShowBuilder(true);
						}}
						className="px-3 py-1 text-xs bg-primary text-primary-foreground rounded hover:opacity-90 cursor-pointer"
					>
						Open Builder
					</button>
				</div>
				<input
					type="text"
					value={formData.show_folder_format}
					onChange={(e) =>
						setFormData({
							...formData,
							show_folder_format: e.target.value,
						})
					}
					className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary font-mono text-xs"
				/>
				<div className="mt-2 p-2 bg-muted rounded border border-border">
					<p className="text-xs font-semibold text-muted-foreground mb-1">
						Example:
					</p>
					<p className="text-xs font-mono">
						Show Title (2024) [tvdbid-67890]
					</p>
				</div>
			</div>

			{/* Show File Naming Format */}
			<div>
				<div className="flex justify-between items-center mb-2">
					<label className="block text-sm font-semibold">
						Show File Naming Format
					</label>
					<button
						type="button"
						onClick={() => {
							setActiveField("file");
							setShowBuilder(true);
						}}
						className="px-3 py-1 text-xs bg-primary text-primary-foreground rounded hover:opacity-90 cursor-pointer"
					>
						Open Builder
					</button>
				</div>
				<input
					type="text"
					value={formData.show_naming_format}
					onChange={(e) =>
						setFormData({
							...formData,
							show_naming_format: e.target.value,
						})
					}
					className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary font-mono text-xs"
				/>
				<div className="mt-2 p-2 bg-muted rounded border border-border">
					<p className="text-xs font-semibold text-muted-foreground mb-1">
						Example:
					</p>
					<p className="text-xs font-mono">
						Show Title - S01E01 - Episode Title
					</p>
				</div>
			</div>

			{/* Naming Builder Modal */}
			{showBuilder && (
				<div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
					<div className="bg-card border border-border rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-hidden">
						<div className="p-4 border-b border-border flex justify-between items-center">
							<h3 className="font-semibold text-lg">
								TV Show{" "}
								{activeField === "folder" ? "Folder" : "File"}{" "}
								Naming Builder
							</h3>
							<button
								type="button"
								onClick={() => setShowBuilder(false)}
								className="text-muted-foreground hover:text-foreground cursor-pointer"
							>
								<X className="w-5 h-5" />
							</button>
						</div>

						<div className="p-4 overflow-y-auto max-h-[calc(90vh-120px)]">
							{/* Presets */}
							<div className="mb-6">
								<h4 className="font-semibold text-sm mb-2">
									Quick Presets
								</h4>
								<div className="flex flex-wrap gap-2">
									{SHOW_PRESETS.map((preset) => (
										<button
											key={preset.name}
											type="button"
											onClick={() => applyPreset(preset)}
											className="px-3 py-1.5 text-xs bg-muted hover:bg-muted/80 rounded-lg cursor-pointer"
										>
											{preset.name}
										</button>
									))}
								</div>
							</div>

							{/* Current Format */}
							<div className="mb-6">
								<h4 className="font-semibold text-sm mb-2">
									Current Format
								</h4>
								<textarea
									value={
										activeField === "folder"
											? formData.show_folder_format
											: formData.show_naming_format
									}
									onChange={(e) => {
										if (activeField === "folder") {
											setFormData({
												...formData,
												show_folder_format:
													e.target.value,
											});
										} else {
											setFormData({
												...formData,
												show_naming_format:
													e.target.value,
											});
										}
									}}
									className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary font-mono text-xs"
									rows={3}
								/>
							</div>

							{/* Available Tokens */}
							<div>
								<h4 className="font-semibold text-sm mb-2">
									Available Tokens
								</h4>
								<div className="grid grid-cols-1 md:grid-cols-2 gap-2">
									{SHOW_TOKENS.map((item) => (
										<button
											key={item.token}
											type="button"
											onClick={() =>
												insertToken(item.token)
											}
											className="flex flex-col items-start p-3 bg-muted/50 hover:bg-muted rounded-lg border border-border cursor-pointer text-left"
										>
											<code className="text-xs font-mono text-primary">
												{item.token}
											</code>
											<span className="text-xs text-muted-foreground mt-1">
												{item.description}
											</span>
											<span className="text-xs text-muted-foreground/70 mt-0.5">
												e.g., {item.example}
											</span>
										</button>
									))}
								</div>
							</div>
						</div>

						<div className="p-4 border-t border-border flex justify-end">
							<button
								type="button"
								onClick={() => setShowBuilder(false)}
								className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 cursor-pointer"
							>
								Done
							</button>
						</div>
					</div>
				</div>
			)}
		</div>
	);
}
