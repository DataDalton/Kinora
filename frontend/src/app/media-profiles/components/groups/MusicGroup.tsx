"use client";
import NamingPreview from "../shared/NamingPreview";

import { useState } from "react";
import { X } from "lucide-react";
import { MediaProfileFormData, MusicTab } from "../types";
import { INDEXERS_BY_TYPE, MUSIC_PRESETS } from "../constants";

const AUDIO_QUALITIES = [
	{ value: "flac", label: "FLAC", description: "Lossless" },
	{ value: "mp3_320", label: "MP3 320", description: "320 kbps" },
	{ value: "mp3_256", label: "MP3 256", description: "256 kbps" },
	{ value: "mp3_128", label: "MP3 128", description: "128 kbps" },
	{ value: "aac", label: "AAC", description: "Lossy" },
	{ value: "ogg", label: "OGG", description: "Vorbis" },
];

const MUSIC_TOKENS = [
	{ token: "{artist}", description: "Artist name", example: "Pink Floyd" },
	{
		token: "{album}",
		description: "Album name",
		example: "The Dark Side of the Moon",
	},
	{ token: "{year}", description: "Release year", example: "1973" },
	{ token: "{track}", description: "Track number", example: "1" },
	{
		token: "{track:00}",
		description: "Track number (2 digits)",
		example: "01",
	},
	{ token: "{disc}", description: "Disc number", example: "1" },
	{
		token: "{disc:00}",
		description: "Disc number (2 digits)",
		example: "01",
	},
	{ token: "{title}", description: "Track title", example: "Speak to Me" },
	{ token: "{genre}", description: "Genre", example: "Progressive Rock" },
	{
		token: "{albumartist}",
		description: "Album artist",
		example: "Pink Floyd",
	},
	{ token: "{bitrate}", description: "Audio bitrate", example: "320" },
	{ token: "{format}", description: "Audio format", example: "FLAC" },
	{
		token: "{quality}",
		description: "Quality descriptor",
		example: "Lossless",
	},
];

type FieldType = "artist" | "album" | "track" | "multiDisc";

interface MusicGroupProps {
	formData: MediaProfileFormData;
	setFormData: (data: MediaProfileFormData) => void;
	activeTab: MusicTab;
}

export default function MusicGroup({
	formData,
	setFormData,
	activeTab,
}: MusicGroupProps) {
	const [showBuilder, setShowBuilder] = useState(false);
	const [activeField, setActiveField] = useState<FieldType>("track");

	const getFieldValue = (field: FieldType): string => {
		switch (field) {
			case "artist":
				return formData.music_artist_folder_format;
			case "album":
				return formData.music_album_folder_format;
			case "track":
				return formData.music_track_naming_format;
			case "multiDisc":
				return formData.music_multi_disc_format;
		}
	};

	const setFieldValue = (field: FieldType, value: string) => {
		switch (field) {
			case "artist":
				setFormData({ ...formData, music_artist_folder_format: value });
				break;
			case "album":
				setFormData({ ...formData, music_album_folder_format: value });
				break;
			case "track":
				setFormData({ ...formData, music_track_naming_format: value });
				break;
			case "multiDisc":
				setFormData({ ...formData, music_multi_disc_format: value });
				break;
		}
	};

	const insertToken = (token: string) => {
		setFieldValue(activeField, getFieldValue(activeField) + token);
	};

	const getFieldTitle = (field: FieldType): string => {
		switch (field) {
			case "artist":
				return "Artist Folder";
			case "album":
				return "Album Folder";
			case "track":
				return "Track";
			case "multiDisc":
				return "Multi-Disc Track";
		}
	};

	const renderIndexersTab = () => (
		<div className="space-y-6">
			<div className="bg-pink-500/20 border border-pink-500/30 rounded-lg p-4 mb-4">
				<h4 className="font-semibold text-sm mb-2">Music Indexers</h4>
				<p className="text-xs text-muted-foreground">
					Configure indexers for music searches. Higher priority =
					searched first.
				</p>
			</div>

			<div>
				<label className="block text-sm font-semibold mb-2">
					Music Indexers
				</label>
				<p className="text-xs text-muted-foreground mb-2">
					Indexers for music searches
				</p>
				<div className="flex flex-wrap gap-2 p-3 bg-muted/50 rounded-lg border border-border">
					{INDEXERS_BY_TYPE.music.map((indexer) => {
						const index = formData.music_indexers.indexOf(indexer);
						const isSelected = index !== -1;
						return (
							<button
								key={indexer}
								type="button"
								onClick={() => {
									if (isSelected) {
										setFormData({
											...formData,
											music_indexers:
												formData.music_indexers.filter(
													(i) => i !== indexer,
												),
										});
									} else {
										setFormData({
											...formData,
											music_indexers: [
												...formData.music_indexers,
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
			<div className="bg-pink-500/20 border border-pink-500/30 rounded-lg p-4 mb-4">
				<h4 className="font-semibold text-sm mb-2">
					Music Quality Settings
				</h4>
				<p className="text-xs text-muted-foreground">
					Configure music download preferences including audio quality
					and metadata embedding.
				</p>
			</div>

			<div>
				<label className="block text-sm font-semibold mb-2">
					Preferred Audio Quality
				</label>
				<p className="text-xs text-muted-foreground mb-3">
					Select allowed formats in order of preference
				</p>
				<div className="grid grid-cols-2 md:grid-cols-3 gap-3">
					{AUDIO_QUALITIES.map((quality) => {
						const isSelected =
							formData.music_preferred_quality.includes(
								quality.value,
							);
						const position =
							formData.music_preferred_quality.indexOf(
								quality.value,
							);
						return (
							<button
								key={quality.value}
								type="button"
								onClick={() => {
									if (isSelected) {
										setFormData({
											...formData,
											music_preferred_quality:
												formData.music_preferred_quality.filter(
													(q) => q !== quality.value,
												),
										});
									} else {
										setFormData({
											...formData,
											music_preferred_quality: [
												...formData.music_preferred_quality,
												quality.value,
											],
										});
									}
								}}
								className={`relative flex flex-col items-center gap-1 p-4 rounded-xl border-2 cursor-pointer transition-all ${
									isSelected
										? "bg-primary/10 border-primary shadow-md"
										: "bg-muted/30 border-border hover:border-muted-foreground/30 hover:bg-muted/50"
								}`}
							>
								{isSelected && (
									<span className="absolute top-2 left-2 w-5 h-5 rounded-full bg-primary text-primary-foreground text-xs flex items-center justify-center font-bold">
										{position + 1}
									</span>
								)}
								<span className="font-semibold text-sm">
									{quality.label}
								</span>
								<span className="text-xs text-muted-foreground">
									{quality.description}
								</span>
							</button>
						);
					})}
				</div>
			</div>

			<div className="space-y-4">
				<h4 className="font-semibold text-sm">Metadata Embedding</h4>

				<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
					<button
						type="button"
						onClick={() =>
							setFormData({
								...formData,
								music_embed_lyrics:
									!formData.music_embed_lyrics,
							})
						}
						className={`flex items-center gap-3 p-4 rounded-xl border-2 cursor-pointer transition-all ${
							formData.music_embed_lyrics
								? "bg-primary/10 border-primary"
								: "bg-muted/30 border-border hover:border-muted-foreground/30"
						}`}
					>
						<div
							className={`w-6 h-6 rounded-full border-2 flex items-center justify-center ${
								formData.music_embed_lyrics
									? "bg-primary border-primary"
									: "border-muted-foreground/30"
							}`}
						>
							{formData.music_embed_lyrics && (
								<svg
									className="w-4 h-4 text-primary-foreground"
									fill="none"
									viewBox="0 0 24 24"
									stroke="currentColor"
								>
									<path
										strokeLinecap="round"
										strokeLinejoin="round"
										strokeWidth={3}
										d="M5 13l4 4L19 7"
									/>
								</svg>
							)}
						</div>
						<div className="text-left">
							<div className="font-semibold text-sm">
								Embed Lyrics
							</div>
							<div className="text-xs text-muted-foreground">
								Include lyrics in audio file metadata
							</div>
						</div>
					</button>

					<button
						type="button"
						onClick={() =>
							setFormData({
								...formData,
								music_embed_artwork:
									!formData.music_embed_artwork,
							})
						}
						className={`flex items-center gap-3 p-4 rounded-xl border-2 cursor-pointer transition-all ${
							formData.music_embed_artwork
								? "bg-primary/10 border-primary"
								: "bg-muted/30 border-border hover:border-muted-foreground/30"
						}`}
					>
						<div
							className={`w-6 h-6 rounded-full border-2 flex items-center justify-center ${
								formData.music_embed_artwork
									? "bg-primary border-primary"
									: "border-muted-foreground/30"
							}`}
						>
							{formData.music_embed_artwork && (
								<svg
									className="w-4 h-4 text-primary-foreground"
									fill="none"
									viewBox="0 0 24 24"
									stroke="currentColor"
								>
									<path
										strokeLinecap="round"
										strokeLinejoin="round"
										strokeWidth={3}
										d="M5 13l4 4L19 7"
									/>
								</svg>
							)}
						</div>
						<div className="text-left">
							<div className="font-semibold text-sm">
								Embed Album Artwork
							</div>
							<div className="text-xs text-muted-foreground">
								Include album art in audio file metadata
							</div>
						</div>
					</button>
				</div>
			</div>
		</div>
	);

	const renderNamingTab = () => (
		<div className="space-y-4">
			<div>
				<div className="flex justify-between items-center mb-2">
					<label className="block text-sm font-semibold">
						Artist Folder Format
					</label>
					<button
						type="button"
						onClick={() => {
							setActiveField("artist");
							setShowBuilder(true);
						}}
						className="px-3 py-1 text-xs bg-primary text-primary-foreground rounded hover:opacity-90 cursor-pointer"
					>
						Open Builder
					</button>
				</div>
				<input
					type="text"
					value={formData.music_artist_folder_format}
					onChange={(e) =>
						setFormData({
							...formData,
							music_artist_folder_format: e.target.value,
						})
					}
					className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary font-mono text-xs"
				/>
				<NamingPreview
					mediaType="music"
					folderFormat={formData.music_album_folder_format}
					namingFormat={formData.music_track_naming_format}
				/>
			</div>

			<div>
				<div className="flex justify-between items-center mb-2">
					<label className="block text-sm font-semibold">
						Album Folder Format
					</label>
					<button
						type="button"
						onClick={() => {
							setActiveField("album");
							setShowBuilder(true);
						}}
						className="px-3 py-1 text-xs bg-primary text-primary-foreground rounded hover:opacity-90 cursor-pointer"
					>
						Open Builder
					</button>
				</div>
				<input
					type="text"
					value={formData.music_album_folder_format}
					onChange={(e) =>
						setFormData({
							...formData,
							music_album_folder_format: e.target.value,
						})
					}
					className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary font-mono text-xs"
				/>
				<NamingPreview
					mediaType="music"
					folderFormat={formData.music_album_folder_format}
					namingFormat={formData.music_track_naming_format}
				/>
			</div>

			<div>
				<div className="flex justify-between items-center mb-2">
					<label className="block text-sm font-semibold">
						Track Naming Format
					</label>
					<button
						type="button"
						onClick={() => {
							setActiveField("track");
							setShowBuilder(true);
						}}
						className="px-3 py-1 text-xs bg-primary text-primary-foreground rounded hover:opacity-90 cursor-pointer"
					>
						Open Builder
					</button>
				</div>
				<input
					type="text"
					value={formData.music_track_naming_format}
					onChange={(e) =>
						setFormData({
							...formData,
							music_track_naming_format: e.target.value,
						})
					}
					className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary font-mono text-xs"
				/>
				<NamingPreview
					mediaType="music"
					folderFormat={formData.music_album_folder_format}
					namingFormat={formData.music_track_naming_format}
				/>
			</div>

			<div>
				<div className="flex justify-between items-center mb-2">
					<label className="block text-sm font-semibold">
						Multi-Disc Track Format
					</label>
					<button
						type="button"
						onClick={() => {
							setActiveField("multiDisc");
							setShowBuilder(true);
						}}
						className="px-3 py-1 text-xs bg-primary text-primary-foreground rounded hover:opacity-90 cursor-pointer"
					>
						Open Builder
					</button>
				</div>
				<input
					type="text"
					value={formData.music_multi_disc_format}
					onChange={(e) =>
						setFormData({
							...formData,
							music_multi_disc_format: e.target.value,
						})
					}
					className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary font-mono text-xs"
				/>
				<NamingPreview
					mediaType="music"
					folderFormat={formData.music_album_folder_format}
					namingFormat={formData.music_track_naming_format}
				/>
			</div>

			{showBuilder && (
				<div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
					<div className="bg-card border border-border rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-hidden">
						<div className="p-4 border-b border-border flex justify-between items-center">
							<h3 className="font-semibold text-lg">
								Music {getFieldTitle(activeField)} Naming
								Builder
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
									{MUSIC_PRESETS[activeField].map(
										(preset) => (
											<button
												key={preset.name}
												type="button"
												onClick={() =>
													setFieldValue(
														activeField,
														preset.format,
													)
												}
												className="px-3 py-1.5 text-xs bg-muted hover:bg-muted/80 rounded-lg cursor-pointer"
											>
												{preset.name}
											</button>
										),
									)}
								</div>
							</div>

							<div className="mb-6">
								<h4 className="font-semibold text-sm mb-2">
									Current Format
								</h4>
								<textarea
									value={getFieldValue(activeField)}
									onChange={(e) =>
										setFieldValue(
											activeField,
											e.target.value,
										)
									}
									className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary font-mono text-xs"
									rows={3}
								/>
							</div>

							<div>
								<h4 className="font-semibold text-sm mb-2">
									Available Tokens
								</h4>
								<div className="grid grid-cols-1 md:grid-cols-2 gap-2">
									{MUSIC_TOKENS.map((item) => (
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

	return (
		<div>
			{activeTab === "indexers" && renderIndexersTab()}
			{activeTab === "quality" && renderQualityTab()}
			{activeTab === "naming" && renderNamingTab()}
		</div>
	);
}
