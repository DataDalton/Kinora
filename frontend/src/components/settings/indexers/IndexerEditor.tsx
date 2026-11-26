"use client";

import { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
	AlertCircle,
	ArrowLeft,
	CheckCircle,
	FileJson,
	FlaskConical,
	Gauge,
	KeyRound,
	Loader2,
	Music,
	Plug,
	Rss,
	Save,
	Search,
	Server,
	ShieldCheck,
	X,
} from "lucide-react";
import ConfirmModal from "@/components/ConfirmModal";
import { useModalDismiss } from "@/hooks/useModalDismiss";
import {
	CREDENTIAL_MASK,
	checkDefinition,
	createIndexer,
	testUnsavedIndexer,
	updateIndexer,
	validationErrors,
} from "@/lib/api/indexers";
import IndexerTestPanel from "./IndexerTestPanel";
import type {
	CustomIndexer,
	DefinitionCheckResult,
	IndexerKind,
	IndexerKindInfo,
	IndexerScope,
	IndexerTemplate,
	IndexerTestResult,
	IndexerWrite,
	TrustTier,
} from "@/types/indexer";

export const SCOPES: { id: IndexerScope; name: string }[] = [
	{ id: "movies", name: "Movies" },
	{ id: "shows", name: "TV Shows" },
	{ id: "anime", name: "Anime" },
	{ id: "music", name: "Music" },
];

export const TRUST_TIERS: {
	id: TrustTier;
	name: string;
	description: string;
}[] = [
	{
		id: "open",
		name: "Open",
		description:
			"Only profiles on the Open safety template download from this indexer",
	},
	{
		id: "balanced",
		name: "Balanced",
		description:
			"A balanced source. Profiles on the Balanced and Open templates download from it",
	},
	{
		id: "trusted",
		name: "Trusted",
		description:
			"Every release counts as a trusted upload, so all three templates download from it",
	},
];

type SectionId =
	| "connection"
	| "definition"
	| "search"
	| "trust"
	| "limits"
	| "test";

// Editor sections in sidebar order. Definition only shows for definition indexers.
const SECTIONS: {
	id: SectionId;
	label: string;
	icon: React.ComponentType<{ className?: string }>;
}[] = [
	{ id: "connection", label: "Connection", icon: Plug },
	{ id: "definition", label: "Definition", icon: FileJson },
	{ id: "search", label: "Search", icon: Search },
	{ id: "trust", label: "Trust", icon: ShieldCheck },
	{ id: "limits", label: "Limits", icon: Gauge },
	{ id: "test", label: "Test", icon: FlaskConical },
];

const KIND_ICONS: Partial<
	Record<IndexerKind, React.ComponentType<{ className?: string }>>
> = {
	unit3d: Server,
	gazelle: Music,
	torznab: Search,
	rss: Rss,
	definition: FileJson,
};

interface Draft {
	name: string;
	kind: IndexerKind;
	baseUrl: string;
	settings: Record<string, string>;
	categories: Record<IndexerScope, string>;
	credentials: Record<string, string>;
	definitionText: string;
	mediaTypes: IndexerScope[];
	enableSearch: boolean;
	enableRss: boolean;
	trustTier: TrustTier;
	isPrivate: boolean;
	minRatio: string;
	minSeedHours: string;
	requestsPerMinute: string;
	minIntervalSeconds: string;
}

function emptyCategories(): Record<IndexerScope, string> {
	return { movies: "", shows: "", anime: "", music: "" };
}

function draftFromIndexer(indexer: CustomIndexer): Draft {
	const settings: Record<string, string> = {};
	for (const [key, value] of Object.entries(indexer.settings || {})) {
		if (key !== "categories" && value !== null && value !== undefined) {
			settings[key] = String(value);
		}
	}
	const categories = emptyCategories();
	for (const scope of SCOPES) {
		categories[scope.id] = (
			indexer.settings?.categories?.[scope.id] || []
		).join(", ");
	}
	return {
		name: indexer.name,
		kind: indexer.kind,
		baseUrl: indexer.base_url,
		settings,
		categories,
		credentials: { ...indexer.credentials },
		definitionText: indexer.definition
			? JSON.stringify(indexer.definition, null, 2)
			: "",
		mediaTypes: [...indexer.media_types],
		enableSearch: indexer.enable_search,
		enableRss: indexer.enable_rss,
		trustTier: indexer.trust_tier,
		isPrivate: indexer.is_private,
		minRatio: indexer.min_ratio !== null ? String(indexer.min_ratio) : "",
		minSeedHours:
			indexer.min_seed_minutes !== null
				? String(
						Math.round((indexer.min_seed_minutes / 60) * 100) / 100,
					)
				: "",
		requestsPerMinute:
			indexer.requests_per_minute !== null
				? String(indexer.requests_per_minute)
				: "",
		minIntervalSeconds: String(indexer.min_interval_seconds),
	};
}

function newDraft(kind: IndexerKind, definitionText = ""): Draft {
	let baseUrl = "";
	let name = "";
	if (definitionText) {
		try {
			const parsed = JSON.parse(definitionText);
			baseUrl = typeof parsed.baseUrl === "string" ? parsed.baseUrl : "";
			name = typeof parsed.name === "string" ? parsed.name : "";
		} catch {
			// The text is shown as it is and checked on save.
		}
	}
	return {
		name,
		kind,
		baseUrl,
		settings: {},
		categories: emptyCategories(),
		credentials: {},
		definitionText,
		mediaTypes: kind === "gazelle" ? ["music"] : ["movies", "shows"],
		enableSearch: true,
		enableRss: false,
		trustTier: "open",
		isPrivate: true,
		minRatio: "",
		minSeedHours: "",
		requestsPerMinute: "",
		minIntervalSeconds: "2",
	};
}

function toNumber(text: string): number | null {
	if (text.trim() === "") return null;
	const value = Number(text);
	return Number.isFinite(value) ? value : null;
}

function toWrite(draft: Draft): IndexerWrite {
	const categories: Record<string, string[]> = {};
	for (const scope of SCOPES) {
		const ids = draft.categories[scope.id]
			.split(",")
			.map((part) => part.trim())
			.filter(Boolean);
		if (ids.length) categories[scope.id] = ids;
	}
	const minSeedHours = toNumber(draft.minSeedHours);
	const requestsPerMinute = toNumber(draft.requestsPerMinute);
	return {
		name: draft.name.trim(),
		kind: draft.kind,
		base_url: draft.baseUrl.trim(),
		settings: { ...draft.settings, categories },
		credentials: draft.credentials,
		definition: draft.kind === "definition" ? draft.definitionText : null,
		media_types: draft.mediaTypes,
		enable_search: draft.enableSearch,
		enable_rss: draft.enableRss,
		trust_tier: draft.trustTier,
		is_private: draft.isPrivate,
		min_ratio: toNumber(draft.minRatio),
		min_seed_minutes:
			minSeedHours !== null ? Math.round(minSeedHours * 60) : null,
		requests_per_minute:
			requestsPerMinute !== null ? Math.round(requestsPerMinute) : null,
		min_interval_seconds: toNumber(draft.minIntervalSeconds) ?? 0,
	};
}

// Credential fields a definition declares, read from the text as typed.
function definitionCredentials(text: string): { key: string; label: string }[] {
	try {
		const parsed = JSON.parse(text);
		if (!Array.isArray(parsed?.credentials)) return [];
		return parsed.credentials
			.map((entry: unknown) =>
				typeof entry === "string"
					? { key: entry, label: entry }
					: entry && typeof entry === "object" && "key" in entry
						? {
								key: String((entry as { key: unknown }).key),
								label: String(
									(entry as { label?: unknown }).label ??
										(entry as { key: unknown }).key,
								),
							}
						: null,
			)
			.filter(Boolean);
	} catch {
		return [];
	}
}

const inputClass =
	"w-full px-3 py-2 border-input bg-background text-foreground border rounded-lg text-sm";

function Toggle({
	enabled,
	onChange,
	disabled = false,
	title,
}: {
	enabled: boolean;
	onChange: (value: boolean) => void;
	disabled?: boolean;
	title: string;
}) {
	return (
		<button
			type="button"
			onClick={() => !disabled && onChange(!enabled)}
			disabled={disabled}
			className={`relative inline-flex h-6 w-11 flex-shrink-0 items-center rounded-full transition-colors cursor-pointer disabled:opacity-50 ${
				enabled ? "bg-primary" : "bg-muted"
			}`}
			title={title}
		>
			<span
				className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
					enabled ? "translate-x-6" : "translate-x-1"
				}`}
			/>
		</button>
	);
}

export { Toggle };

// A setting with a switch beside its title and description. The whole card is the
// switch, so a click anywhere on it toggles the setting. The switch keeps its full
// width however narrow the card gets.
function ToggleCard({
	title,
	description,
	enabled,
	onChange,
	disabled = false,
}: {
	title: string;
	description: string;
	enabled: boolean;
	onChange: (value: boolean) => void;
	disabled?: boolean;
}) {
	return (
		<button
			type="button"
			role="switch"
			aria-checked={enabled}
			onClick={() => onChange(!enabled)}
			disabled={disabled}
			className={`w-full text-left flex items-center justify-between gap-4 p-4 rounded-lg border border-border transition ${
				disabled
					? "cursor-not-allowed"
					: "hover:bg-muted/80 cursor-pointer"
			}`}
		>
			<div className="min-w-0">
				<p className="text-sm font-medium">{title}</p>
				<p className="text-xs text-muted-foreground mt-1">
					{description}
				</p>
			</div>
			<span
				className={`relative inline-flex h-6 w-11 flex-shrink-0 items-center rounded-full transition-colors ${
					enabled ? "bg-primary" : "bg-muted"
				} ${disabled ? "opacity-50" : ""}`}
			>
				<span
					className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
						enabled ? "translate-x-6" : "translate-x-1"
					}`}
				/>
			</span>
		</button>
	);
}

interface IndexerEditorProps {
	indexer: CustomIndexer | null;
	kinds: IndexerKindInfo[];
	templates: IndexerTemplate[];
	onClose: () => void;
	onSaved: (indexer: CustomIndexer) => void;
}

// Adds or edits one user-defined indexer. A new indexer starts by choosing its type,
// and a definition indexer can start from one of the example definitions.
export default function IndexerEditor({
	indexer,
	kinds,
	templates,
	onClose,
	onSaved,
}: IndexerEditorProps) {
	const [draft, setDraft] = useState<Draft | null>(
		indexer ? draftFromIndexer(indexer) : null,
	);
	// The draft as it was when editing started, to tell whether anything changed.
	const [baseline, setBaseline] = useState<Draft | null>(draft);
	const [section, setSection] = useState<SectionId>("connection");
	// Close action waiting on the discard confirmation, if any.
	const [pendingClose, setPendingClose] = useState<(() => void) | null>(null);
	const [errors, setErrors] = useState<string[]>([]);
	const [testQuery, setTestQuery] = useState("");
	const [testResult, setTestResult] = useState<IndexerTestResult | null>(
		null,
	);
	const [definitionCheck, setDefinitionCheck] =
		useState<DefinitionCheckResult | null>(null);

	const kindInfo = useMemo(
		() => kinds.find((kind) => kind.kind === draft?.kind),
		[kinds, draft?.kind],
	);

	const saveMutation = useMutation({
		mutationFn: async (current: Draft) =>
			indexer
				? updateIndexer(indexer.id, toWrite(current))
				: createIndexer(toWrite(current)),
		onSuccess: (saved) => onSaved(saved),
		onError: (error) => setErrors(validationErrors(error)),
	});

	const testMutation = useMutation({
		mutationFn: async (current: Draft) =>
			testUnsavedIndexer(
				toWrite(current),
				indexer?.id ?? null,
				testQuery,
			),
		onMutate: () => {
			setErrors([]);
			setTestResult(null);
		},
		onSuccess: (result) => setTestResult(result),
		onError: (error) => setErrors(validationErrors(error)),
	});

	const checkMutation = useMutation({
		mutationFn: async (text: string) => checkDefinition(text),
		onSuccess: (result) => setDefinitionCheck(result),
		onError: (error) =>
			setDefinitionCheck({
				valid: false,
				errors: validationErrors(error),
				credentials: [],
			}),
	});

	const busy = saveMutation.isPending || testMutation.isPending;
	const isDirty =
		draft !== null && JSON.stringify(draft) !== JSON.stringify(baseline);

	// Runs a close action, first asking to discard changes when anything was edited.
	const requestClose = (action: () => void) => {
		if (isDirty) {
			setPendingClose(() => action);
		} else {
			action();
		}
	};

	const backdropProps = useModalDismiss({
		onClose: () => requestClose(onClose),
		closeOnOutsideClick: true,
		disabled: busy || pendingClose !== null,
	});

	const update = (changes: Partial<Draft>) =>
		setDraft((current) => (current ? { ...current, ...changes } : current));

	const credentialFields =
		draft?.kind === "definition"
			? definitionCredentials(draft.definitionText).map((field) => ({
					key: field.key,
					label: field.label,
					help: "",
					placeholder: "",
				}))
			: (kindInfo?.credentials || []).map((field) => ({
					key: field.key,
					label: field.label,
					help: field.help,
					placeholder: field.placeholder,
				}));

	const settingFields = (kindInfo?.settings || []).filter(
		(field) => field.kind !== "categories",
	);
	const hasCategories =
		draft?.kind === "definition" ||
		(kindInfo?.settings || []).some((field) => field.kind === "categories");

	const startDraft = (next: Draft) => {
		setDraft(next);
		setBaseline(next);
		setSection("connection");
		setErrors([]);
		setTestResult(null);
		setDefinitionCheck(null);
	};

	const kindPicker = (
		<div className="flex-1 overflow-y-auto p-6 space-y-6">
			<div className="bg-blue-500/20 border border-blue-500/30 rounded-lg p-4">
				<h4 className="font-semibold text-sm mb-2">
					Choose the indexer type
				</h4>
				<p className="text-xs text-muted-foreground">
					Pick the software the site runs. Sites on anything else are
					added through a Kinora definition, starting blank or from an
					example.
				</p>
			</div>

			<div>
				<h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
					Tracker software
				</h3>
				<div className="grid grid-cols-1 md:grid-cols-2 gap-3">
					{kinds
						.filter((kind) => kind.kind !== "definition")
						.map((kind) => {
							const Icon = KIND_ICONS[kind.kind] || Server;
							return (
								<button
									key={kind.kind}
									type="button"
									onClick={() =>
										startDraft(newDraft(kind.kind))
									}
									className="flex items-start gap-3 text-left p-4 rounded-lg border-2 border-border hover:border-primary/50 hover:bg-muted/50 transition-all cursor-pointer"
								>
									<div className="p-2 bg-primary/10 rounded-lg flex-shrink-0">
										<Icon className="w-5 h-5 text-primary" />
									</div>
									<div>
										<p className="text-sm font-semibold">
											{kind.label}
										</p>
										<p className="text-xs text-muted-foreground mt-1">
											{kind.description}
										</p>
									</div>
								</button>
							);
						})}
				</div>
			</div>

			<div>
				<h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">
					Kinora definition
				</h3>
				<p className="text-xs text-muted-foreground mb-3">
					For any other site. Start from an example and adjust its
					URLs, selectors and fields. Examples are documentation only
					and are never searched until saved as an indexer.
				</p>
				<div className="grid grid-cols-1 md:grid-cols-3 gap-3">
					<button
						type="button"
						onClick={() => startDraft(newDraft("definition"))}
						className="flex items-start gap-3 text-left p-4 rounded-lg border-2 border-border hover:border-primary/50 hover:bg-muted/50 transition-all cursor-pointer"
					>
						<div className="p-2 bg-muted rounded-lg flex-shrink-0">
							<FileJson className="w-5 h-5" />
						</div>
						<div>
							<p className="text-sm font-semibold">
								Blank definition
							</p>
							<p className="text-xs text-muted-foreground mt-1">
								Write the definition from scratch
							</p>
						</div>
					</button>
					{templates.map((template) => (
						<button
							key={template.id}
							type="button"
							onClick={() =>
								startDraft(
									newDraft(
										"definition",
										JSON.stringify(
											template.definition,
											null,
											2,
										),
									),
								)
							}
							className="flex items-start gap-3 text-left p-4 rounded-lg border-2 border-border hover:border-primary/50 hover:bg-muted/50 transition-all cursor-pointer"
						>
							<div className="p-2 bg-muted rounded-lg flex-shrink-0">
								<FileJson className="w-5 h-5" />
							</div>
							<div>
								<p className="text-sm font-semibold">
									{template.label}
								</p>
								<p className="text-xs text-muted-foreground mt-1">
									{template.description}
								</p>
							</div>
						</button>
					))}
				</div>
			</div>
		</div>
	);

	const sections = SECTIONS.filter(
		(item) => item.id !== "definition" || draft?.kind === "definition",
	);
	const activeSection =
		sections.find((item) => item.id === section) || sections[0];

	const intro = (title: string, text: string) => (
		<div className="bg-blue-500/20 border border-blue-500/30 rounded-lg p-4">
			<h4 className="font-semibold text-sm mb-2">{title}</h4>
			<p className="text-xs text-muted-foreground">{text}</p>
		</div>
	);

	const connectionSection = draft && (
		<div className="space-y-6">
			{intro(
				"Connection",
				"Where the indexer lives and how Kinora signs in to it.",
			)}
			<div className="p-4 rounded-lg border border-border space-y-4">
				<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
					<div>
						<label className="block text-sm font-medium mb-1">
							Name
						</label>
						<input
							type="text"
							value={draft.name}
							onChange={(e) => update({ name: e.target.value })}
							placeholder="Shown in search results and history"
							className={inputClass}
						/>
					</div>
					<div>
						<label className="block text-sm font-medium mb-1">
							{draft.kind === "torznab" ? "API URL" : "Base URL"}
						</label>
						<input
							type="text"
							value={draft.baseUrl}
							onChange={(e) =>
								update({ baseUrl: e.target.value })
							}
							placeholder={
								draft.kind === "torznab"
									? "https://tracker.example/api/torznab"
									: draft.kind === "rss"
										? "Taken from the feed URL when empty"
										: "https://tracker.example"
							}
							className={inputClass}
						/>
					</div>
				</div>
				{settingFields.length > 0 && (
					<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
						{settingFields.map((field) => (
							<div key={field.key}>
								<label className="block text-sm font-medium mb-1">
									{field.label}
								</label>
								<input
									type="text"
									value={draft.settings[field.key] ?? ""}
									placeholder={field.placeholder}
									onChange={(e) =>
										update({
											settings: {
												...draft.settings,
												[field.key]: e.target.value,
											},
										})
									}
									className={inputClass}
								/>
								{field.help && (
									<p className="text-xs text-muted-foreground mt-1">
										{field.help}
									</p>
								)}
							</div>
						))}
					</div>
				)}
			</div>

			{credentialFields.length > 0 ? (
				<div className="p-4 rounded-lg border border-border space-y-4">
					<div>
						<h3 className="font-semibold text-sm flex items-center gap-2">
							<KeyRound className="w-4 h-4" />
							Credentials
						</h3>
						<p className="text-xs text-muted-foreground mt-1">
							Stored encrypted and never shown again. Leave a
							saved value as it is to keep it.
						</p>
					</div>
					<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
						{credentialFields.map((field) => (
							<div key={field.key}>
								<label className="block text-sm font-medium mb-1">
									{field.label}
								</label>
								<input
									type="password"
									autoComplete="new-password"
									value={draft.credentials[field.key] ?? ""}
									placeholder={field.placeholder}
									onFocus={() => {
										if (
											draft.credentials[field.key] ===
											CREDENTIAL_MASK
										) {
											update({
												credentials: {
													...draft.credentials,
													[field.key]: "",
												},
											});
										}
									}}
									onBlur={() => {
										if (
											indexer?.credentials[field.key] ===
												CREDENTIAL_MASK &&
											!draft.credentials[field.key]
										) {
											update({
												credentials: {
													...draft.credentials,
													[field.key]:
														CREDENTIAL_MASK,
												},
											});
										}
									}}
									onChange={(e) =>
										update({
											credentials: {
												...draft.credentials,
												[field.key]: e.target.value,
											},
										})
									}
									className={inputClass}
								/>
								{field.help && (
									<p className="text-xs text-muted-foreground mt-1">
										{field.help}
									</p>
								)}
							</div>
						))}
					</div>
				</div>
			) : (
				draft.kind === "definition" && (
					<p className="text-xs text-muted-foreground">
						Credentials appear here once the definition lists them
						in its credentials field.
					</p>
				)
			)}
		</div>
	);

	const definitionSection = draft && (
		<div className="space-y-6">
			{intro(
				"Definition",
				"The JSON that tells Kinora how to search the site and read its results. Put secrets in the credentials list and refer to them as variables such as {apiKey}, so they are stored encrypted instead of in the definition text.",
			)}
			<div className="p-4 rounded-lg border border-border space-y-3">
				<div className="flex items-center justify-between">
					<label className="block text-sm font-medium">
						Definition (JSON)
					</label>
					<button
						type="button"
						onClick={() =>
							checkMutation.mutate(draft.definitionText)
						}
						disabled={
							checkMutation.isPending || !draft.definitionText
						}
						className="flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg bg-muted hover:bg-muted/80 transition cursor-pointer disabled:opacity-50"
					>
						{checkMutation.isPending ? (
							<Loader2 className="w-4 h-4 animate-spin" />
						) : (
							<CheckCircle className="w-4 h-4" />
						)}
						Check definition
					</button>
				</div>
				<textarea
					value={draft.definitionText}
					onChange={(e) => {
						update({ definitionText: e.target.value });
						setDefinitionCheck(null);
					}}
					rows={22}
					spellCheck={false}
					className={`${inputClass} font-mono`}
				/>
				{definitionCheck && (
					<div
						className={`p-3 rounded-lg border text-sm ${
							definitionCheck.valid
								? "bg-green-500/10 border-green-500/20"
								: "bg-red-500/10 border-red-500/20"
						}`}
					>
						{definitionCheck.valid ? (
							<p className="flex items-center gap-2 text-green-500">
								<CheckCircle className="w-4 h-4" />
								The definition is valid
							</p>
						) : (
							<ul className="space-y-1">
								{definitionCheck.errors.map(
									(message, index) => (
										<li
											key={index}
											className="flex items-start gap-2 text-red-500"
										>
											<AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
											{message}
										</li>
									),
								)}
							</ul>
						)}
					</div>
				)}
			</div>
		</div>
	);

	const searchSection = draft && (
		<div className="space-y-6">
			{intro(
				"Search",
				"Which media this indexer is searched for, the categories it is searched in, and whether it feeds RSS monitoring.",
			)}
			<div className="p-4 rounded-lg border border-border space-y-3">
				<h3 className="font-semibold text-sm">Media types</h3>
				<div className="flex flex-wrap gap-2">
					{SCOPES.map((scope) => {
						const selected = draft.mediaTypes.includes(scope.id);
						return (
							<button
								key={scope.id}
								type="button"
								onClick={() =>
									update({
										mediaTypes: selected
											? draft.mediaTypes.filter(
													(id) => id !== scope.id,
												)
											: [...draft.mediaTypes, scope.id],
									})
								}
								className={`px-4 py-2 rounded-lg font-medium text-sm transition-colors cursor-pointer ${
									selected
										? "bg-primary text-primary-foreground"
										: "bg-muted hover:bg-muted/80 text-foreground"
								}`}
							>
								{scope.name}
							</button>
						);
					})}
				</div>
			</div>

			{hasCategories && (
				<div className="p-4 rounded-lg border border-border space-y-3">
					<div>
						<h3 className="font-semibold text-sm">Categories</h3>
						<p className="text-xs text-muted-foreground mt-1">
							Category ids searched per media type, separated by
							commas. Empty uses{" "}
							{draft.kind === "definition"
								? "the definition's categories"
								: "the defaults shown"}
							.
						</p>
					</div>
					{draft.mediaTypes.length === 0 ? (
						<p className="text-sm text-muted-foreground">
							Choose a media type above to set its categories.
						</p>
					) : (
						<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
							{SCOPES.filter((scope) =>
								draft.mediaTypes.includes(scope.id),
							).map((scope) => (
								<div key={scope.id}>
									<label className="block text-sm font-medium mb-1">
										{scope.name}
									</label>
									<input
										type="text"
										value={draft.categories[scope.id]}
										placeholder={(
											kindInfo?.default_categories?.[
												scope.id
											] || []
										).join(", ")}
										onChange={(e) =>
											update({
												categories: {
													...draft.categories,
													[scope.id]: e.target.value,
												},
											})
										}
										className={inputClass}
									/>
								</div>
							))}
						</div>
					)}
				</div>
			)}

			<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
				<ToggleCard
					title="Search"
					description="Automatic and interactive searches"
					enabled={draft.enableSearch}
					onChange={(value) => update({ enableSearch: value })}
				/>
				<ToggleCard
					title="RSS"
					description={
						kindInfo?.supports_rss === false
							? "This type has no feed"
							: "New uploads for RSS monitoring"
					}
					enabled={draft.enableRss}
					onChange={(value) => update({ enableRss: value })}
					disabled={kindInfo?.supports_rss === false}
				/>
			</div>
		</div>
	);

	const trustSection = draft && (
		<div className="space-y-6">
			{intro(
				"Trust",
				"How far profiles trust releases from this indexer. Each profile's safety template decides which tiers it downloads from.",
			)}
			<div className="grid grid-cols-1 md:grid-cols-3 gap-3">
				{TRUST_TIERS.map((tier) => {
					const selected = draft.trustTier === tier.id;
					return (
						<button
							key={tier.id}
							type="button"
							onClick={() => update({ trustTier: tier.id })}
							className={`p-4 rounded-lg border-2 text-left transition-all cursor-pointer ${
								selected
									? "border-primary bg-primary/10"
									: "border-border hover:border-muted-foreground/50"
							}`}
						>
							<p
								className={`font-medium text-sm mb-2 ${selected ? "text-primary" : ""}`}
							>
								{tier.name}
							</p>
							<p className="text-xs text-muted-foreground">
								{tier.description}
							</p>
						</button>
					);
				})}
			</div>
			<ToggleCard
				title="Private tracker"
				description="Magnets carry the passkey, so they stay on the server"
				enabled={draft.isPrivate}
				onChange={(value) => update({ isPrivate: value })}
			/>
		</div>
	);

	const limitsSection = draft && (
		<div className="space-y-6">
			{intro(
				"Limits",
				"Seeding minimums that protect your ratio on this tracker, and how fast Kinora may send it requests.",
			)}
			<div className="p-4 rounded-lg border border-border space-y-4">
				<div>
					<h3 className="font-semibold text-sm">Seeding minimum</h3>
					<p className="text-xs text-muted-foreground mt-1">
						Torrents from this indexer are never paused or removed
						by seeding limits until every minimum set here is met.
						Global and profile limits apply after that.
					</p>
				</div>
				<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
					<div>
						<label className="block text-sm font-medium mb-1">
							Minimum ratio
						</label>
						<input
							type="number"
							min={0}
							step="0.1"
							value={draft.minRatio}
							placeholder="No minimum"
							onChange={(e) =>
								update({ minRatio: e.target.value })
							}
							className={inputClass}
						/>
					</div>
					<div>
						<label className="block text-sm font-medium mb-1">
							Minimum seed time (hours)
						</label>
						<input
							type="number"
							min={0}
							step="1"
							value={draft.minSeedHours}
							placeholder="No minimum"
							onChange={(e) =>
								update({ minSeedHours: e.target.value })
							}
							className={inputClass}
						/>
					</div>
				</div>
			</div>
			<div className="p-4 rounded-lg border border-border space-y-4">
				<div>
					<h3 className="font-semibold text-sm">Request limits</h3>
					<p className="text-xs text-muted-foreground mt-1">
						Shared by every search, RSS check and download from this
						indexer.
					</p>
				</div>
				<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
					<div>
						<label className="block text-sm font-medium mb-1">
							Requests per minute
						</label>
						<input
							type="number"
							min={1}
							step="1"
							value={draft.requestsPerMinute}
							placeholder="No limit"
							onChange={(e) =>
								update({ requestsPerMinute: e.target.value })
							}
							className={inputClass}
						/>
					</div>
					<div>
						<label className="block text-sm font-medium mb-1">
							Seconds between requests
						</label>
						<input
							type="number"
							min={0}
							step="0.5"
							value={draft.minIntervalSeconds}
							onChange={(e) =>
								update({ minIntervalSeconds: e.target.value })
							}
							className={inputClass}
						/>
					</div>
				</div>
			</div>
		</div>
	);

	const testSection = draft && (
		<div className="space-y-6">
			{intro(
				"Test",
				"Checks the connection and credentials, then runs one search and shows what was parsed. Nothing is saved or downloaded.",
			)}
			<div className="p-4 rounded-lg border border-border space-y-4">
				<div className="flex gap-2">
					<input
						type="text"
						value={testQuery}
						onChange={(e) => setTestQuery(e.target.value)}
						onKeyDown={(e) => {
							if (e.key === "Enter" && !busy) {
								testMutation.mutate(draft);
							}
						}}
						placeholder="Sample search, or empty for the newest uploads"
						className={inputClass}
					/>
					<button
						type="button"
						onClick={() => testMutation.mutate(draft)}
						disabled={busy}
						className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition cursor-pointer disabled:opacity-50 whitespace-nowrap"
					>
						{testMutation.isPending ? (
							<Loader2 className="w-4 h-4 animate-spin" />
						) : (
							<FlaskConical className="w-4 h-4" />
						)}
						Run test
					</button>
				</div>
				{testMutation.isPending && (
					<p className="text-sm text-muted-foreground">
						Testing the indexer...
					</p>
				)}
				{testResult && (
					<IndexerTestPanel
						result={testResult}
						onClose={() => setTestResult(null)}
					/>
				)}
			</div>
		</div>
	);

	const sectionContent: Record<SectionId, React.ReactNode> = {
		connection: connectionSection,
		definition: definitionSection,
		search: searchSection,
		trust: trustSection,
		limits: limitsSection,
		test: testSection,
	};

	const editorBody = draft && (
		<div className="flex flex-1 overflow-hidden">
			{/* Section navigation */}
			<div className="w-56 flex-shrink-0 bg-muted/30 border-r border-border overflow-y-auto">
				<div className="p-2 space-y-1">
					{sections.map((item) => {
						const Icon = item.icon;
						const isActive = activeSection.id === item.id;
						return (
							<button
								key={item.id}
								type="button"
								onClick={() => setSection(item.id)}
								className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all cursor-pointer ${
									isActive
										? "bg-primary text-primary-foreground font-medium shadow-sm"
										: "text-foreground hover:bg-muted/50"
								}`}
							>
								<Icon className="w-5 h-5 flex-shrink-0" />
								<span className="text-sm truncate">
									{item.label}
								</span>
							</button>
						);
					})}
				</div>
			</div>

			{/* Section content */}
			<div className="flex-1 overflow-y-auto p-6">
				{sectionContent[activeSection.id]}
			</div>
		</div>
	);

	return (
		<div
			className="fixed inset-0 backdrop-blur-sm bg-background/50 z-[60] flex items-center justify-center p-4"
			{...backdropProps}
		>
			<div className="bg-background rounded-lg max-w-5xl w-full h-[90vh] flex flex-col overflow-hidden border border-border shadow-2xl">
				{/* Header */}
				<div className="flex items-center justify-between px-6 py-4 border-b border-border">
					<div className="flex items-center gap-3">
						{!indexer && draft && (
							<button
								type="button"
								onClick={() =>
									requestClose(() => setDraft(null))
								}
								className="p-1.5 bg-muted rounded hover:bg-muted/80 transition cursor-pointer"
								title="Choose another type"
							>
								<ArrowLeft className="w-4 h-4" />
							</button>
						)}
						<div>
							<h2 className="text-xl font-bold">
								{indexer
									? `Edit ${indexer.name}`
									: draft
										? `New ${kindInfo?.label || "indexer"}`
										: "Add indexer"}
							</h2>
							{draft && (
								<p className="text-xs text-muted-foreground">
									{kindInfo?.label || draft.kind}
									{draft.name.trim()
										? `, ${draft.name.trim()}`
										: ""}
								</p>
							)}
						</div>
					</div>
					<button
						type="button"
						onClick={() => requestClose(onClose)}
						disabled={busy}
						className="p-1.5 bg-muted rounded hover:bg-muted/80 transition cursor-pointer disabled:opacity-50"
						title="Close"
					>
						<X className="w-4 h-4" />
					</button>
				</div>

				{draft ? editorBody : kindPicker}

				{/* Footer */}
				{draft && (
					<div className="border-t border-border px-6 py-4 space-y-3">
						{errors.length > 0 && (
							<div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-sm max-h-40 overflow-y-auto">
								<ul className="space-y-1">
									{errors.map((message, index) => (
										<li
											key={index}
											className="flex items-start gap-2 text-red-500"
										>
											<AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
											{message}
										</li>
									))}
								</ul>
							</div>
						)}
						<div className="flex items-center justify-between gap-2">
							<p className="text-xs text-muted-foreground">
								{!draft.name.trim()
									? "A name is required before saving"
									: isDirty
										? "Unsaved changes"
										: ""}
							</p>
							<div className="flex gap-2">
								<button
									type="button"
									onClick={() => requestClose(onClose)}
									disabled={busy}
									className="flex items-center gap-2 px-4 py-2 bg-muted text-foreground rounded-lg hover:bg-muted/80 transition cursor-pointer disabled:opacity-50"
								>
									Cancel
								</button>
								<button
									type="button"
									onClick={() => {
										setErrors([]);
										saveMutation.mutate(draft);
									}}
									disabled={busy || !draft.name.trim()}
									className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition cursor-pointer disabled:opacity-50"
								>
									{saveMutation.isPending ? (
										<Loader2 className="w-4 h-4 animate-spin" />
									) : (
										<Save className="w-4 h-4" />
									)}
									Save
								</button>
							</div>
						</div>
					</div>
				)}
			</div>

			<ConfirmModal
				isOpen={pendingClose !== null}
				title="Discard changes"
				message="This indexer has changes that are not saved. Closing throws them away."
				confirmText="Discard"
				variant="warning"
				onConfirm={() => {
					const close = pendingClose;
					setPendingClose(null);
					close?.();
				}}
				onCancel={() => setPendingClose(null)}
			/>
		</div>
	);
}
