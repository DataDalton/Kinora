"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { MediaProfileFormData } from "../types";
import {
	RESOLUTIONS,
	VIDEO_CODECS,
	SOURCES,
	AUDIO_CODECS,
	AUDIO_CHANNELS,
	HDR_FORMATS,
	SPECIAL_EDITIONS,
	MOVIE_PRESETS,
	INDEXERS_BY_TYPE,
} from "../constants";
import QualityCheckboxList from "../shared/QualityCheckboxList";

interface MoviesGroupProps {
	formData: MediaProfileFormData;
	setFormData: (data: MediaProfileFormData) => void;
	activeTab: "indexers" | "quality" | "naming";
}

const MOVIE_TOKENS = [
	{
		token: "{Movie Title}",
		description: "Full movie title",
		example: "The Dark Knight",
	},
	{
		token: "{Movie CleanTitle}",
		description: "Clean title without special chars",
		example: "The Dark Knight",
	},
	{
		token: "{Movie TitleThe}",
		description: 'Title with "The" at end',
		example: "Dark Knight, The",
	},
	{
		token: "{Release Year}",
		description: "Movie release year",
		example: "2008",
	},
	{ token: "{TmdbId}", description: "TMDB database ID", example: "155" },
	{
		token: "{ImdbId}",
		description: "IMDB database ID",
		example: "tt0468569",
	},
	{
		token: "{Edition Tags}",
		description: "Edition info",
		example: "IMAX Extended",
	},
	{
		token: "{Quality Full}",
		description: "Full quality string",
		example: "Bluray-1080p",
	},
	{
		token: "{Quality Title}",
		description: "Quality title",
		example: "Bluray 1080p",
	},
	{
		token: "{Quality Source}",
		description: "Source type",
		example: "Bluray",
	},
	{
		token: "{Quality Resolution}",
		description: "Resolution",
		example: "1080p",
	},
	{
		token: "{MediaInfo VideoCodec}",
		description: "Video codec",
		example: "x265",
	},
	{
		token: "{MediaInfo VideoBitDepth}",
		description: "Bit depth",
		example: "10",
	},
	{
		token: "{MediaInfo VideoDynamicRangeType}",
		description: "HDR type",
		example: "HDR10",
	},
	{
		token: "{MediaInfo AudioCodec}",
		description: "Audio codec",
		example: "DTS-HD MA",
	},
	{
		token: "{MediaInfo AudioChannels}",
		description: "Audio channels",
		example: "5.1",
	},
	{
		token: "{MediaInfo AudioLanguages}",
		description: "Audio languages",
		example: "EN",
	},
	{
		token: "{MediaInfo SubtitleLanguages}",
		description: "Subtitle languages",
		example: "EN ES",
	},
	{
		token: "{Release Group}",
		description: "Release group name",
		example: "SPARKS",
	},
];

const formatSize = (mb: number | null): string => {
	if (mb === null || mb === 0) return "0 MB";
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

export default function MoviesGroup({
	formData,
	setFormData,
	activeTab,
}: MoviesGroupProps) {
	const [showBuilder, setShowBuilder] = useState(false);
	const [activeField, setActiveField] = useState<"folder" | "file">("file");

	const insertToken = (token: string) => {
		if (activeField === "folder") {
			setFormData({
				...formData,
				movie_folder_format: formData.movie_folder_format + token,
			});
		} else {
			setFormData({
				...formData,
				movie_naming_format: formData.movie_naming_format + token,
			});
		}
	};

	const applyPreset = (preset: (typeof MOVIE_PRESETS)[0]) => {
		setFormData({
			...formData,
			movie_folder_format: preset.folder,
			movie_naming_format: preset.file,
		});
	};

	return (
		<div className="space-y-6">
			{activeTab === "indexers" && (
				<div className="space-y-6">
					<div className="bg-blue-500/20 border border-blue-500/30 rounded-lg p-4 mb-4">
						<h4 className="font-semibold text-sm mb-2">
							Movie Indexer Selection
						</h4>
						<p className="text-xs text-muted-foreground">
							Select which indexers to use for movie searches.
							Indexers are searched in priority order.
						</p>
					</div>

					<div>
						<label className="block text-sm font-semibold mb-2">
							Movie Indexers
						</label>
						<p className="text-xs text-muted-foreground mb-2">
							Indexers for movie searches
						</p>
						<div className="flex flex-wrap gap-2 p-3 bg-muted/50 rounded-lg border border-border">
							{INDEXERS_BY_TYPE.movies.map((indexer) => {
								const index =
									formData.movie_indexers.indexOf(indexer);
								const isSelected = index !== -1;
								return (
									<button
										key={indexer}
										type="button"
										onClick={() => {
											if (isSelected) {
												setFormData({
													...formData,
													movie_indexers:
														formData.movie_indexers.filter(
															(i) =>
																i !== indexer,
														),
												});
											} else {
												setFormData({
													...formData,
													movie_indexers: [
														...formData.movie_indexers,
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
			)}

			{activeTab === "quality" && (
				<div className="space-y-6">
					<div className="bg-blue-500/20 border border-blue-500/30 rounded-lg p-4 mb-4">
						<h4 className="font-semibold text-sm mb-2">
							Movie Quality Settings
						</h4>
						<p className="text-xs text-muted-foreground">
							Configure quality preferences specifically for
							movies. Select all acceptable options.
						</p>
					</div>

					{/* Resolutions */}
					<QualityCheckboxList
						items={RESOLUTIONS}
						selected={formData.movie_resolutions}
						onChange={(items) =>
							setFormData({
								...formData,
								movie_resolutions: items,
							})
						}
						label="Resolutions"
						description="Select all acceptable resolutions for movies"
					/>

					{/* Video Codecs */}
					<QualityCheckboxList
						items={VIDEO_CODECS}
						selected={formData.movie_codecs}
						onChange={(items) =>
							setFormData({ ...formData, movie_codecs: items })
						}
						label="Video Codecs"
						description="Select all acceptable video codecs for movies"
					/>

					{/* Sources */}
					<QualityCheckboxList
						items={SOURCES}
						selected={formData.movie_sources}
						onChange={(items) =>
							setFormData({ ...formData, movie_sources: items })
						}
						label="Sources"
						description="Select all acceptable source types for movies"
					/>

					{/* Audio Codecs */}
					<QualityCheckboxList
						items={AUDIO_CODECS}
						selected={formData.movie_audio_codecs}
						onChange={(items) =>
							setFormData({
								...formData,
								movie_audio_codecs: items,
							})
						}
						label="Audio Codecs"
						description="Select all acceptable audio codecs for movies"
					/>

					{/* Audio Channels */}
					<QualityCheckboxList
						items={AUDIO_CHANNELS}
						selected={formData.movie_audio_channels}
						onChange={(items) =>
							setFormData({
								...formData,
								movie_audio_channels: items,
							})
						}
						label="Audio Channels"
						description="Select all acceptable audio channel configurations for movies"
					/>

					{/* HDR Formats */}
					<QualityCheckboxList
						items={HDR_FORMATS}
						selected={formData.movie_hdr_formats}
						onChange={(items) =>
							setFormData({
								...formData,
								movie_hdr_formats: items,
							})
						}
						label="HDR Formats"
						description="Select all acceptable HDR formats for movies"
					/>

					{/* Special Editions */}
					<QualityCheckboxList
						items={SPECIAL_EDITIONS}
						selected={formData.movie_editions}
						onChange={(items) =>
							setFormData({ ...formData, movie_editions: items })
						}
						label="Special Editions"
						description="Select all acceptable special editions for movies"
					/>

					{/* Size Limits */}
					<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
						<div>
							<label className="block text-sm font-semibold mb-2">
								Minimum Size
							</label>
							<div className="space-y-2">
								<input
									type="range"
									min="0"
									max="102400"
									step="100"
									value={formData.movie_min_size || 0}
									onChange={(e) => {
										const newMin = parseInt(e.target.value);
										setFormData({
											...formData,
											movie_min_size: newMin,
											movie_max_size:
												formData.movie_max_size &&
												formData.movie_max_size < newMin
													? newMin
													: formData.movie_max_size,
										});
									}}
									className="w-full h-2 bg-background rounded-lg appearance-none cursor-pointer accent-primary"
								/>
								<input
									type="text"
									value={formatSize(formData.movie_min_size)}
									onChange={(e) => {
										const newMin = parseSizeInput(
											e.target.value,
										);
										setFormData({
											...formData,
											movie_min_size: newMin,
											movie_max_size:
												formData.movie_max_size &&
												formData.movie_max_size < newMin
													? newMin
													: formData.movie_max_size,
										});
									}}
									className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary"
									placeholder="e.g., 500 MB or 2 GB"
								/>
							</div>
							<p className="text-xs text-muted-foreground mt-1">
								Minimum file size for movies
							</p>
						</div>

						<div>
							<label className="block text-sm font-semibold mb-2">
								Maximum Size
							</label>
							<div className="space-y-2">
								<input
									type="range"
									min={formData.movie_min_size || 0}
									max="102400"
									step="100"
									value={
										formData.movie_max_size ||
										formData.movie_min_size ||
										0
									}
									onChange={(e) => {
										const newMax = parseInt(e.target.value);
										setFormData({
											...formData,
											movie_max_size: Math.max(
												newMax,
												formData.movie_min_size || 0,
											),
										});
									}}
									className="w-full h-2 bg-background rounded-lg appearance-none cursor-pointer accent-primary"
								/>
								<input
									type="text"
									value={formatSize(formData.movie_max_size)}
									onChange={(e) => {
										const newMax = parseSizeInput(
											e.target.value,
										);
										setFormData({
											...formData,
											movie_max_size: Math.max(
												newMax,
												formData.movie_min_size || 0,
											),
										});
									}}
									className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary"
									placeholder="e.g., 5 GB or 5000 MB"
								/>
							</div>
							<p className="text-xs text-muted-foreground mt-1">
								Maximum file size for movies
							</p>
						</div>
					</div>
				</div>
			)}

			{activeTab === "naming" && (
				<div className="space-y-4">
					<div className="bg-blue-500/20 border border-blue-500/30 rounded-lg p-4 mb-4">
						<h4 className="font-semibold text-sm mb-2">
							Movie Naming Configuration
						</h4>
						<p className="text-xs text-muted-foreground">
							Configure how movie files and folders are named
							using tokens and presets.
						</p>
					</div>

					{/* Movie Folder Format */}
					<div>
						<div className="flex justify-between items-center mb-2">
							<label className="block text-sm font-semibold">
								Movie Folder Format
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
							value={formData.movie_folder_format}
							onChange={(e) =>
								setFormData({
									...formData,
									movie_folder_format: e.target.value,
								})
							}
							className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary font-mono text-xs"
						/>
						<div className="mt-2 p-2 bg-muted rounded border border-border">
							<p className="text-xs font-semibold text-muted-foreground mb-1">
								Example:
							</p>
							<p className="text-xs font-mono">
								Movie Title (2024) [tmdbid-12345]
							</p>
						</div>
					</div>

					{/* Movie File Naming Format */}
					<div>
						<div className="flex justify-between items-center mb-2">
							<label className="block text-sm font-semibold">
								Movie File Naming Format
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
						<textarea
							value={formData.movie_naming_format}
							onChange={(e) =>
								setFormData({
									...formData,
									movie_naming_format: e.target.value,
								})
							}
							className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary font-mono text-xs"
							rows={2}
						/>
						<div className="mt-2 p-2 bg-muted rounded border border-border">
							<p className="text-xs font-semibold text-muted-foreground mb-1">
								Example:
							</p>
							<p className="text-xs font-mono">
								Movie Title (2024) [tmdbid-12345] -
								[Bluray-1080p][DTS 5.1][x265]-GROUP
							</p>
						</div>
					</div>

					{/* Naming Builder Modal */}
					{showBuilder && (
						<div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
							<div className="bg-card border border-border rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-hidden">
								<div className="p-4 border-b border-border flex justify-between items-center">
									<h3 className="font-semibold text-lg">
										Movie{" "}
										{activeField === "folder"
											? "Folder"
											: "File"}{" "}
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
											{MOVIE_PRESETS.map((preset) => (
												<button
													key={preset.name}
													type="button"
													onClick={() =>
														applyPreset(preset)
													}
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
													? formData.movie_folder_format
													: formData.movie_naming_format
											}
											onChange={(e) => {
												if (activeField === "folder") {
													setFormData({
														...formData,
														movie_folder_format:
															e.target.value,
													});
												} else {
													setFormData({
														...formData,
														movie_naming_format:
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
											{MOVIE_TOKENS.map((item) => (
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
			)}
		</div>
	);
}
