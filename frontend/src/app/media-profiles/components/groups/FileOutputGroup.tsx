"use client";

import { MediaProfileFormData } from "../types";
import { DEFAULT_NAMING } from "../constants";

interface FileOutputGroupProps {
	formData: MediaProfileFormData;
	setFormData: (data: MediaProfileFormData) => void;
}

export default function FileOutputGroup({
	formData,
	setFormData,
}: FileOutputGroupProps) {
	// Selecting Jellyfin applies the Jellyfin Default naming presets to every media type.
	const selectJellyfin = () => {
		setFormData({
			...formData,
			media_server: "jellyfin",
			movie_folder_format: DEFAULT_NAMING.movie.folder,
			movie_naming_format: DEFAULT_NAMING.movie.file,
			show_folder_format: DEFAULT_NAMING.show.folder,
			show_naming_format: DEFAULT_NAMING.show.file,
			anime_folder_format: DEFAULT_NAMING.anime.folder,
			anime_naming_format: DEFAULT_NAMING.anime.file,
		});
	};

	return (
		<div className="space-y-6">
			<div>
				<label className="block text-sm font-semibold mb-2">
					Media Server
				</label>
				<div className="flex gap-2">
					<button
						type="button"
						onClick={selectJellyfin}
						className={`flex-1 px-4 py-2.5 rounded-lg font-medium transition-all cursor-pointer ${
							formData.media_server === "jellyfin"
								? "bg-primary text-primary-foreground shadow-md"
								: "bg-muted text-muted-foreground hover:bg-muted/80"
						}`}
					>
						Jellyfin
					</button>
					<button
						type="button"
						onClick={() =>
							setFormData({ ...formData, media_server: "custom" })
						}
						className={`flex-1 px-4 py-2.5 rounded-lg font-medium transition-all cursor-pointer ${
							formData.media_server === "custom"
								? "bg-primary text-primary-foreground shadow-md"
								: "bg-muted text-muted-foreground hover:bg-muted/80"
						}`}
					>
						Custom
					</button>
				</div>
				<p className="text-xs text-muted-foreground mt-1">
					Jellyfin applies optimized naming with TMDB IDs and folder
					structure, and writes NFO metadata. Custom keeps your
					per-type naming formats.
				</p>
			</div>

			<div className="p-4 bg-muted/50 rounded-lg border border-border">
				<label className="block text-sm font-semibold mb-2">
					File Management
				</label>
				<div className="flex gap-2">
					<button
						type="button"
						onClick={() =>
							setFormData({ ...formData, use_hardlinks: true })
						}
						className={`flex-1 px-4 py-2.5 rounded-lg font-medium transition-all cursor-pointer ${
							formData.use_hardlinks
								? "bg-primary text-primary-foreground shadow-md"
								: "bg-muted text-muted-foreground hover:bg-muted/80"
						}`}
					>
						Use Hardlinks
					</button>
					<button
						type="button"
						onClick={() =>
							setFormData({ ...formData, use_hardlinks: false })
						}
						className={`flex-1 px-4 py-2.5 rounded-lg font-medium transition-all cursor-pointer ${
							!formData.use_hardlinks
								? "bg-primary text-primary-foreground shadow-md"
								: "bg-muted text-muted-foreground hover:bg-muted/80"
						}`}
					>
						Copy Files
					</button>
				</div>
				<p className="text-xs text-muted-foreground mt-1">
					Hardlinks save disk space and allow continued seeding. Use
					Copy if source and destination are on different drives.
				</p>
			</div>

			<div>
				<h4 className="font-semibold text-sm mb-3">
					Character Replacement
				</h4>
				<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
					<div>
						<label className="block text-sm font-semibold mb-2">
							Illegal Character Replacement
						</label>
						<input
							type="text"
							value={formData.illegal_char_replacement}
							onChange={(e) =>
								setFormData({
									...formData,
									illegal_char_replacement: e.target.value,
								})
							}
							className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary"
							placeholder="_"
							maxLength={5}
						/>
						<p className="text-xs text-muted-foreground mt-1">
							Replace illegal filename characters (/, \, *, ?, ",
							&lt;, &gt;, |)
						</p>
					</div>

					<div>
						<label className="block text-sm font-semibold mb-2">
							Colon Replacement
						</label>
						<input
							type="text"
							value={formData.colon_replacement}
							onChange={(e) =>
								setFormData({
									...formData,
									colon_replacement: e.target.value,
								})
							}
							className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary"
							placeholder=" -"
							maxLength={5}
						/>
						<p className="text-xs text-muted-foreground mt-1">
							Replace colons in filenames (common in movie titles)
						</p>
					</div>
				</div>
			</div>
		</div>
	);
}
