"use client";
import NamingPreview from "../shared/NamingPreview";

import { useState } from "react";
import { X } from "lucide-react";
import { MediaProfileFormData } from "../types";
import { QualityCheckboxList } from "../shared";
import {
	RESOLUTIONS,
	VIDEO_CODECS,
	SOURCES,
	AUDIO_CODECS,
	AUDIO_CHANNELS,
	HDR_FORMATS,
	SHOW_PRESETS,
	INDEXERS_BY_TYPE,
} from "../constants";

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

const formatSize = (mb: number): string => {
	if (mb === 0) return "0 MB";
	if (mb >= 1024) {
		return `${(mb / 1024).toFixed(1)} GB`;
	}
	return `${mb} MB`;
};

const parseSizeInput = (value: string): number => {
	const match = value.match(/^(\d+(?:\.\d+)?)\s*(GB|MB)?$/i);
	if (!match) return 0;
	const num = parseFloat(match[1]);
	const unit = match[2]?.toUpperCase();
	if (unit === "GB") return Math.round(num * 1024);
	return Math.round(num);
};

interface TVShowsGroupProps {
	formData: MediaProfileFormData;
	setFormData: (data: MediaProfileFormData) => void;
	activeTab: "indexers" | "quality" | "naming" | "options";
}

export default function TVShowsGroup({
	formData,
	setFormData,
	activeTab,
}: TVShowsGroupProps) {
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

	const renderIndexersTab = () => (
		<div className="space-y-6">
			<div className="bg-blue-500/20 border border-blue-500/30 rounded-lg p-4 mb-4">
				<h4 className="font-semibold text-sm mb-2">
					TV Show Indexer Configuration
				</h4>
				<p className="text-xs text-muted-foreground">
					Configure indexer priority for TV shows. Higher priority
					indexers are searched first.
				</p>
			</div>

			<div>
				<label className="block text-sm font-semibold mb-2">
					TV Show Indexers
				</label>
				<p className="text-xs text-muted-foreground mb-2">
					Indexers for TV show searches
				</p>
				<div className="flex flex-wrap gap-2 p-3 bg-muted/50 rounded-lg border border-border">
					{INDEXERS_BY_TYPE.shows.map((indexer) => {
						const index = formData.show_indexers.indexOf(indexer);
						const isSelected = index !== -1;
						return (
							<button
								key={indexer}
								type="button"
								onClick={() => {
									if (isSelected) {
										setFormData({
											...formData,
											show_indexers:
												formData.show_indexers.filter(
													(i) => i !== indexer,
												),
										});
									} else {
										setFormData({
											...formData,
											show_indexers: [
												...formData.show_indexers,
												indexer,
											],
										});
									}
								}}
								className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all cursor-pointer ${
									isSelected
										? "bg-primary/20 border-2 border-primary"
										: "bg-background border border-border hover:border-primary/50"
								}`}
							>
								{isSelected && (
									<span className="text-xs text-muted-foreground">
										#{index + 1}
									</span>
								)}
								<span>{indexer}</span>
							</button>
						);
					})}
				</div>
			</div>
		</div>
	);

	const renderQualityTab = () => (
		<div className="space-y-6">
			<div className="bg-blue-500/20 border border-blue-500/30 rounded-lg p-4 mb-4">
				<h4 className="font-semibold text-sm mb-2">
					TV Show Quality Settings
				</h4>
				<p className="text-xs text-muted-foreground">
					Configure quality preferences specific to TV shows. These
					settings override global quality settings.
				</p>
			</div>

			<QualityCheckboxList
				items={RESOLUTIONS}
				selected={formData.show_resolutions}
				onChange={(items) =>
					setFormData({ ...formData, show_resolutions: items })
				}
				label="TV Show Resolutions"
				description="Select resolutions for TV shows. Higher numbers = better quality."
			/>

			<QualityCheckboxList
				items={VIDEO_CODECS}
				selected={formData.show_codecs}
				onChange={(items) =>
					setFormData({ ...formData, show_codecs: items })
				}
				label="TV Show Video Codecs"
				description="Select video codecs for TV shows."
			/>

			<QualityCheckboxList
				items={SOURCES}
				selected={formData.show_sources}
				onChange={(items) =>
					setFormData({ ...formData, show_sources: items })
				}
				label="TV Show Sources"
				description="Select sources for TV shows."
			/>

			<QualityCheckboxList
				items={AUDIO_CODECS}
				selected={formData.show_audio_codecs}
				onChange={(items) =>
					setFormData({ ...formData, show_audio_codecs: items })
				}
				label="TV Show Audio Codecs"
				description="Select audio codecs for TV shows."
			/>

			<QualityCheckboxList
				items={AUDIO_CHANNELS}
				selected={formData.show_audio_channels}
				onChange={(items) =>
					setFormData({ ...formData, show_audio_channels: items })
				}
				label="TV Show Audio Channels"
				description="Select audio channel configurations for TV shows."
			/>

			<QualityCheckboxList
				items={HDR_FORMATS}
				selected={formData.show_hdr_formats}
				onChange={(items) =>
					setFormData({ ...formData, show_hdr_formats: items })
				}
				label="TV Show HDR Formats"
				description="Select HDR formats for TV shows."
			/>

			<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
				<div>
					<label className="block text-sm font-semibold mb-2">
						Minimum File Size
					</label>
					<div className="space-y-2">
						<input
							type="range"
							min="0"
							max="102400"
							step="100"
							value={formData.show_min_size || 0}
							onChange={(e) => {
								const newMin = parseInt(e.target.value);
								setFormData({
									...formData,
									show_min_size: newMin,
									show_max_size:
										formData.show_max_size &&
										formData.show_max_size < newMin
											? newMin
											: formData.show_max_size,
								});
							}}
							className="w-full h-2 bg-background rounded-lg appearance-none cursor-pointer accent-primary"
						/>
						<input
							type="text"
							value={formatSize(formData.show_min_size || 0)}
							onChange={(e) => {
								const newMin = parseSizeInput(e.target.value);
								setFormData({
									...formData,
									show_min_size: newMin,
									show_max_size:
										formData.show_max_size &&
										formData.show_max_size < newMin
											? newMin
											: formData.show_max_size,
								});
							}}
							className="w-full px-3 py-2 text-sm border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary"
							placeholder="e.g., 500 MB or 2 GB"
						/>
					</div>
					<p className="text-xs text-muted-foreground mt-1">
						Minimum file size for TV episodes
					</p>
				</div>

				<div>
					<label className="block text-sm font-semibold mb-2">
						Maximum File Size
					</label>
					<div className="space-y-2">
						<input
							type="range"
							min={formData.show_min_size || 0}
							max="102400"
							step="100"
							value={
								formData.show_max_size ||
								formData.show_min_size ||
								0
							}
							onChange={(e) => {
								const newMax = parseInt(e.target.value);
								setFormData({
									...formData,
									show_max_size: Math.max(
										newMax,
										formData.show_min_size || 0,
									),
								});
							}}
							className="w-full h-2 bg-background rounded-lg appearance-none cursor-pointer accent-primary"
						/>
						<input
							type="text"
							value={formatSize(formData.show_max_size || 0)}
							onChange={(e) => {
								const newMax = parseSizeInput(e.target.value);
								setFormData({
									...formData,
									show_max_size: Math.max(
										newMax,
										formData.show_min_size || 0,
									),
								});
							}}
							className="w-full px-3 py-2 text-sm border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary"
							placeholder="e.g., 5 GB or 5000 MB"
						/>
					</div>
					<p className="text-xs text-muted-foreground mt-1">
						Maximum file size for TV episodes
					</p>
				</div>
			</div>
		</div>
	);

	const renderNamingTab = () => (
		<div className="space-y-4">
			<div className="bg-blue-500/20 border border-blue-500/30 rounded-lg p-4 mb-4">
				<h4 className="font-semibold text-sm mb-2">
					TV Show Naming Configuration
				</h4>
				<p className="text-xs text-muted-foreground">
					Configure folder structure and file naming format for TV
					shows.
				</p>
			</div>

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
				<NamingPreview
					mediaType="show"
					folderFormat={formData.show_folder_format}
					namingFormat={formData.show_naming_format}
				/>
			</div>

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
				<NamingPreview
					mediaType="show"
					folderFormat={formData.show_folder_format}
					namingFormat={formData.show_naming_format}
				/>
			</div>

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

	const renderOptionsTab = () => (
		<div className="space-y-6">
			<div className="bg-blue-500/20 border border-blue-500/30 rounded-lg p-4 mb-4">
				<h4 className="font-semibold text-sm mb-2">TV Show Options</h4>
				<p className="text-xs text-muted-foreground">
					Configure TV show specific options like season pack
					preferences.
				</p>
			</div>

			<div>
				<label className="block text-sm font-semibold mb-2">
					Season Pack Preference
				</label>
				<p className="text-xs text-muted-foreground mb-2">
					Choose whether to prioritize season packs or individual
					episodes for TV shows
				</p>
				<div className="grid grid-cols-3 gap-2">
					<button
						type="button"
						onClick={() =>
							setFormData({
								...formData,
								season_pack_preference: "prefer",
							})
						}
						className={`px-4 py-2.5 rounded-lg font-medium transition-all cursor-pointer ${
							formData.season_pack_preference === "prefer"
								? "bg-primary text-primary-foreground shadow-md"
								: "bg-muted text-muted-foreground hover:bg-muted/80"
						}`}
					>
						Prefer Season Packs
					</button>
					<button
						type="button"
						onClick={() =>
							setFormData({
								...formData,
								season_pack_preference: "only",
							})
						}
						className={`px-4 py-2.5 rounded-lg font-medium transition-all cursor-pointer ${
							formData.season_pack_preference === "only"
								? "bg-primary text-primary-foreground shadow-md"
								: "bg-muted text-muted-foreground hover:bg-muted/80"
						}`}
					>
						Season Packs Only
					</button>
					<button
						type="button"
						onClick={() =>
							setFormData({
								...formData,
								season_pack_preference: "avoid",
							})
						}
						className={`px-4 py-2.5 rounded-lg font-medium transition-all cursor-pointer ${
							formData.season_pack_preference === "avoid"
								? "bg-primary text-primary-foreground shadow-md"
								: "bg-muted text-muted-foreground hover:bg-muted/80"
						}`}
					>
						Individual Episodes
					</button>
				</div>
				<p className="text-xs text-muted-foreground mt-2">
					{formData.season_pack_preference === "prefer" &&
						"Try season packs first, fall back to individual episodes if not found"}
					{formData.season_pack_preference === "only" &&
						"Only download complete season packs, reject individual episodes"}
					{formData.season_pack_preference === "avoid" &&
						"Only download individual episodes, reject season packs"}
				</p>
			</div>
		</div>
	);

	return (
		<div className="space-y-6">
			{activeTab === "indexers" && renderIndexersTab()}
			{activeTab === "quality" && renderQualityTab()}
			{activeTab === "naming" && renderNamingTab()}
			{activeTab === "options" && renderOptionsTab()}
		</div>
	);
}
