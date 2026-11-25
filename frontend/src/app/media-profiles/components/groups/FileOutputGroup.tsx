"use client";

import { useState } from "react";
import { FilePlus2, Lock, Plus, X } from "lucide-react";
import { MediaProfileFormData } from "../types";
import {
	DEFAULT_NAMING,
	DEFAULT_NEVER_IMPORT_EXTENSIONS,
	FIXED_NEVER_IMPORT_EXTENSIONS,
} from "../constants";

interface FileOutputGroupProps {
	formData: MediaProfileFormData;
	setFormData: (data: MediaProfileFormData) => void;
}

export default function FileOutputGroup({
	formData,
	setFormData,
}: FileOutputGroupProps) {
	const [newNeverImportExt, setNewNeverImportExt] = useState("");
	const neverImport = formData.never_import_extensions || [];

	const addNeverImport = () => {
		const ext = newNeverImportExt.trim().toLowerCase();
		setNewNeverImportExt("");
		if (!ext) return;
		const normalized = ext.startsWith(".") ? ext : `.${ext}`;
		if (
			neverImport.includes(normalized) ||
			FIXED_NEVER_IMPORT_EXTENSIONS.includes(normalized)
		) {
			return;
		}
		setFormData({
			...formData,
			never_import_extensions: [...neverImport, normalized],
		});
	};

	const removeNeverImport = (ext: string) => {
		setFormData({
			...formData,
			never_import_extensions: neverImport.filter((e) => e !== ext),
		});
	};

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

			<div className="p-4 bg-muted/50 rounded-lg border border-border">
				<div className="flex items-center justify-between">
					<div className="flex items-center gap-3">
						<FilePlus2 className="w-5 h-5 text-primary" />
						<div>
							<h3 className="font-semibold text-sm">
								Import Extra Files
							</h3>
							<p className="text-xs text-muted-foreground">
								Bring featurettes, subtitles, images, lyrics,
								cue sheets, rip logs and booklets along with the
								main media
							</p>
						</div>
					</div>
					<button
						type="button"
						onClick={() =>
							setFormData({
								...formData,
								import_extra_files:
									!formData.import_extra_files,
							})
						}
						className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors cursor-pointer ${
							formData.import_extra_files
								? "bg-primary"
								: "bg-muted"
						}`}
					>
						<span
							className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
								formData.import_extra_files
									? "translate-x-6"
									: "translate-x-1"
							}`}
						/>
					</button>
				</div>
			</div>

			<div className="p-4 rounded-lg border border-border">
				<div className="flex items-center justify-between mb-3">
					<div>
						<h3 className="font-semibold text-sm">Never Import</h3>
						<p className="text-xs text-muted-foreground">
							Files with these extensions stay in the download
							folder and are never copied into the library
						</p>
					</div>
					<button
						type="button"
						onClick={() =>
							setFormData({
								...formData,
								never_import_extensions: [
									...DEFAULT_NEVER_IMPORT_EXTENSIONS,
								],
							})
						}
						className="text-xs text-primary hover:underline cursor-pointer"
					>
						Reset to defaults
					</button>
				</div>

				<div className="flex gap-2 mb-3">
					<input
						type="text"
						value={newNeverImportExt}
						onChange={(e) => setNewNeverImportExt(e.target.value)}
						onKeyDown={(e) => {
							if (e.key === "Enter") {
								e.preventDefault();
								addNeverImport();
							}
						}}
						placeholder="e.g., .rar"
						className="flex-1 px-3 py-2 border-input bg-background text-foreground border rounded-lg text-sm"
					/>
					<button
						type="button"
						onClick={addNeverImport}
						className="px-3 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 cursor-pointer"
					>
						<Plus className="w-4 h-4" />
					</button>
				</div>

				<div className="flex flex-wrap gap-2">
					{neverImport.map((ext) => (
						<span
							key={ext}
							className="inline-flex items-center gap-1 px-2 py-1 bg-destructive/20 text-destructive rounded text-sm"
						>
							{ext}
							<button
								type="button"
								onClick={() => removeNeverImport(ext)}
								className="hover:text-destructive/80 cursor-pointer"
							>
								<X className="w-3 h-3" />
							</button>
						</span>
					))}
					{neverImport.length === 0 && (
						<span className="text-xs text-muted-foreground italic">
							Only the fixed entries below are skipped
						</span>
					)}
				</div>

				<p className="text-xs text-muted-foreground mt-4 mb-2">
					Always skipped, for every profile
				</p>
				<div className="flex flex-wrap gap-2">
					{FIXED_NEVER_IMPORT_EXTENSIONS.map((ext) => (
						<span
							key={ext}
							className="inline-flex items-center gap-1 px-2 py-1 bg-muted text-muted-foreground rounded text-sm"
							title="Executables, scripts and shortcuts are never imported"
						>
							<Lock className="w-3 h-3" />
							{ext}
						</span>
					))}
				</div>
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
