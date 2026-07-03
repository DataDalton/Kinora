"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { SectionProps } from "../types";
import { MUSIC_PRESETS } from "../constants";

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

export default function MusicNaming({ formData, setFormData }: SectionProps) {
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

	return (
		<div className="space-y-4">
			{/* Artist Folder Format */}
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
				<div className="mt-2 p-2 bg-muted rounded border border-border">
					<p className="text-xs font-semibold text-muted-foreground mb-1">
						Example:
					</p>
					<p className="text-xs font-mono">Artist Name</p>
				</div>
			</div>

			{/* Album Folder Format */}
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
				<div className="mt-2 p-2 bg-muted rounded border border-border">
					<p className="text-xs font-semibold text-muted-foreground mb-1">
						Example:
					</p>
					<p className="text-xs font-mono">Album Name (2023)</p>
				</div>
			</div>

			{/* Track Naming Format */}
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
				<div className="mt-2 p-2 bg-muted rounded border border-border">
					<p className="text-xs font-semibold text-muted-foreground mb-1">
						Example:
					</p>
					<p className="text-xs font-mono">01 - Track Title.flac</p>
				</div>
			</div>

			{/* Multi-Disc Format */}
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
				<div className="mt-2 p-2 bg-muted rounded border border-border">
					<p className="text-xs font-semibold text-muted-foreground mb-1">
						Example:
					</p>
					<p className="text-xs font-mono">
						01-05 - Track Title.flac
					</p>
				</div>
			</div>

			{/* Naming Builder Modal */}
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
							{/* Presets */}
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

							{/* Current Format */}
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

							{/* Available Tokens */}
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
}
