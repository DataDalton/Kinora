"use client";

import ISO6391 from "iso-639-1";
import { useState } from "react";
import { X } from "lucide-react";
import { MediaProfileFormData } from "../types";
import Validation from "../Profile/Validation";

const LANGUAGES = ISO6391.getAllCodes().map((code) => ({
	code,
	name: ISO6391.getName(code),
	nativeName: ISO6391.getNativeName(code),
}));

interface ProfileGroupProps {
	formData: MediaProfileFormData;
	setFormData: (data: MediaProfileFormData) => void;
	activeTab: "general" | "languages" | "validation";
	hasAttemptedSubmit?: boolean;
}

export default function ProfileGroup({
	formData,
	setFormData,
	activeTab,
	hasAttemptedSubmit,
}: ProfileGroupProps) {
	const [languageSearch, setLanguageSearch] = useState("");
	const [subtitleLanguageSearch, setSubtitleLanguageSearch] = useState("");

	if (activeTab === "general") {
		return (
			<div className="space-y-6">
				{/* Profile Name */}
				<div
					className={`p-4 rounded-lg border-2 ${
						hasAttemptedSubmit && !formData.name.trim()
							? "border-destructive bg-destructive/5"
							: "border-transparent"
					}`}
				>
					<label className="block text-sm font-semibold mb-2">
						Profile Name *
					</label>
					<input
						type="text"
						value={formData.name}
						onChange={(e) =>
							setFormData({ ...formData, name: e.target.value })
						}
						className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary"
						placeholder="e.g., 4K HDR Movies, Standard Quality"
					/>
					{hasAttemptedSubmit && !formData.name.trim() && (
						<p className="text-xs text-destructive mt-1">
							Profile name is required
						</p>
					)}
				</div>

				{/* Upgrade Behavior */}
				<div className="p-4 bg-muted/50 rounded-lg border border-border">
					<label className="block text-sm font-semibold mb-2">
						Upgrade Behavior
					</label>
					<div className="flex gap-2">
						<button
							type="button"
							onClick={() =>
								setFormData({
									...formData,
									upgrade_allowed: true,
								})
							}
							className={`flex-1 px-4 py-2.5 rounded-lg font-medium transition-all cursor-pointer ${
								formData.upgrade_allowed
									? "bg-primary text-primary-foreground shadow-md"
									: "bg-muted text-muted-foreground hover:bg-muted/80"
							}`}
						>
							Auto Upgrade
						</button>
						<button
							type="button"
							onClick={() =>
								setFormData({
									...formData,
									upgrade_allowed: false,
								})
							}
							className={`flex-1 px-4 py-2.5 rounded-lg font-medium transition-all cursor-pointer ${
								!formData.upgrade_allowed
									? "bg-primary text-primary-foreground shadow-md"
									: "bg-muted text-muted-foreground hover:bg-muted/80"
							}`}
						>
							One-Time Grab
						</button>
					</div>
					<p className="text-xs text-muted-foreground mt-1">
						{formData.upgrade_allowed
							? "Automatically upgrade to higher quality over time"
							: "Grab highest quality once and stop"}
					</p>
				</div>
			</div>
		);
	}

	if (activeTab === "languages") {
		return (
			<div className="space-y-6">
				{/* Audio Languages */}
				<div className="space-y-3 p-4 rounded-lg border-2 border-transparent">
					<div>
						<label className="block text-sm font-semibold mb-2">
							Audio Languages
						</label>
						<p className="text-xs text-muted-foreground mb-2">
							Add preferred audio languages in order of priority
						</p>

						<div className="relative mb-3">
							<input
								type="text"
								value={languageSearch}
								onChange={(e) =>
									setLanguageSearch(e.target.value)
								}
								onFocus={() =>
									setLanguageSearch(languageSearch || " ")
								}
								onBlur={() =>
									setTimeout(() => setLanguageSearch(""), 200)
								}
								className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary"
								placeholder="Search languages..."
							/>
							{languageSearch && (
								<div className="absolute z-10 w-full mt-1 bg-background border border-border rounded-lg shadow-lg max-h-48 overflow-y-auto">
									{LANGUAGES.filter(
										(lang) =>
											!formData.languages.includes(
												lang.code,
											) &&
											(lang.name
												.toLowerCase()
												.includes(
													languageSearch
														.trim()
														.toLowerCase(),
												) ||
												lang.code
													.toLowerCase()
													.includes(
														languageSearch
															.trim()
															.toLowerCase(),
													) ||
												(lang.nativeName &&
													lang.nativeName
														.toLowerCase()
														.includes(
															languageSearch
																.trim()
																.toLowerCase(),
														))),
									).map((lang) => (
										<button
											key={lang.code}
											type="button"
											onClick={() => {
												setFormData({
													...formData,
													languages: [
														...formData.languages,
														lang.code,
													],
												});
												setLanguageSearch("");
											}}
											className="w-full px-4 py-2 text-left hover:bg-muted transition-colors cursor-pointer text-sm"
										>
											<span className="font-medium">
												{lang.name}
											</span>
											{lang.nativeName &&
												lang.nativeName !==
													lang.name && (
													<span className="text-xs text-muted-foreground ml-2">
														({lang.nativeName})
													</span>
												)}
											<span className="text-xs text-muted-foreground ml-2">
												{lang.code}
											</span>
										</button>
									))}
								</div>
							)}
						</div>

						{formData.languages.length > 0 && (
							<div className="flex flex-wrap gap-2 p-3 bg-muted rounded-lg border border-border">
								{formData.languages.map((langCode, index) => {
									const lang = LANGUAGES.find(
										(l) => l.code === langCode,
									);
									return (
										<div
											key={langCode}
											className="flex items-center gap-2 px-3 py-1.5 bg-primary/20 border-2 border-primary rounded-lg text-sm font-medium"
										>
											<span className="text-xs text-muted-foreground">
												#{index + 1}
											</span>
											<span>
												{lang?.name || langCode}
											</span>
											<button
												type="button"
												onClick={() => {
													setFormData({
														...formData,
														languages:
															formData.languages.filter(
																(l) =>
																	l !==
																	langCode,
															),
													});
												}}
												className="ml-1 text-muted-foreground hover:text-foreground cursor-pointer"
											>
												<X className="w-3 h-3" />
											</button>
										</div>
									);
								})}
							</div>
						)}
					</div>
				</div>

				{/* Subtitle Languages */}
				<div className="space-y-3 p-4 rounded-lg border-2 border-transparent">
					<div>
						<label className="block text-sm font-semibold mb-2">
							Subtitle Languages
						</label>
						<p className="text-xs text-muted-foreground mb-2">
							Optional: Add subtitle languages to download. Leave
							empty to skip subtitle downloads.
						</p>

						<div className="relative mb-3">
							<input
								type="text"
								value={subtitleLanguageSearch}
								onChange={(e) =>
									setSubtitleLanguageSearch(e.target.value)
								}
								onFocus={() =>
									setSubtitleLanguageSearch(
										subtitleLanguageSearch || " ",
									)
								}
								onBlur={() =>
									setTimeout(
										() => setSubtitleLanguageSearch(""),
										200,
									)
								}
								className="w-full px-4 py-2.5 border-input bg-background text-foreground border rounded-lg focus:ring-2 focus:ring-primary"
								placeholder="Search subtitle languages..."
							/>
							{subtitleLanguageSearch && (
								<div className="absolute z-10 w-full mt-1 bg-background border border-border rounded-lg shadow-lg max-h-48 overflow-y-auto">
									{LANGUAGES.filter(
										(lang) =>
											!formData.subtitle_languages.includes(
												lang.code,
											) &&
											(lang.name
												.toLowerCase()
												.includes(
													subtitleLanguageSearch
														.trim()
														.toLowerCase(),
												) ||
												lang.code
													.toLowerCase()
													.includes(
														subtitleLanguageSearch
															.trim()
															.toLowerCase(),
													) ||
												(lang.nativeName &&
													lang.nativeName
														.toLowerCase()
														.includes(
															subtitleLanguageSearch
																.trim()
																.toLowerCase(),
														))),
									).map((lang) => (
										<button
											key={lang.code}
											type="button"
											onClick={() => {
												setFormData({
													...formData,
													subtitle_languages: [
														...formData.subtitle_languages,
														lang.code,
													],
												});
												setSubtitleLanguageSearch("");
											}}
											className="w-full px-4 py-2 text-left hover:bg-muted transition-colors cursor-pointer text-sm"
										>
											<span className="font-medium">
												{lang.name}
											</span>
											{lang.nativeName &&
												lang.nativeName !==
													lang.name && (
													<span className="text-xs text-muted-foreground ml-2">
														({lang.nativeName})
													</span>
												)}
											<span className="text-xs text-muted-foreground ml-2">
												{lang.code}
											</span>
										</button>
									))}
								</div>
							)}
						</div>

						{formData.subtitle_languages.length > 0 && (
							<div className="flex flex-wrap gap-2 p-3 bg-muted rounded-lg border border-border">
								{formData.subtitle_languages.map(
									(langCode, index) => {
										const lang = LANGUAGES.find(
											(l) => l.code === langCode,
										);
										return (
											<div
												key={langCode}
												className="flex items-center gap-2 px-3 py-1.5 bg-primary/20 border-2 border-primary rounded-lg text-sm font-medium"
											>
												<span className="text-xs text-muted-foreground">
													#{index + 1}
												</span>
												<span>
													{lang?.name || langCode}
												</span>
												<button
													type="button"
													onClick={() => {
														setFormData({
															...formData,
															subtitle_languages:
																formData.subtitle_languages.filter(
																	(l) =>
																		l !==
																		langCode,
																),
														});
													}}
													className="ml-1 text-muted-foreground hover:text-foreground cursor-pointer"
												>
													<X className="w-3 h-3" />
												</button>
											</div>
										);
									},
								)}
							</div>
						)}
					</div>
				</div>
			</div>
		);
	}

	if (activeTab === "validation") {
		return (
			<Validation
				formData={formData}
				setFormData={setFormData}
				hasAttemptedSubmit={hasAttemptedSubmit}
			/>
		);
	}

	return null;
}
