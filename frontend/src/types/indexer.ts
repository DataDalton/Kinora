// User-defined indexers. Field names match the /indexers API JSON.

export type IndexerKind =
	| "unit3d"
	| "gazelle"
	| "torznab"
	| "rss"
	| "definition";
export type IndexerScope = "movies" | "shows" | "anime" | "music";
export type TrustTier = "open" | "balanced" | "trusted";
export type IndexerHealthStatus =
	| "ok"
	| "warning"
	| "failing"
	| "disabled"
	| "untested";

export type IndexerCategories = Partial<Record<IndexerScope, string[]>>;

export interface IndexerSettings {
	categories?: IndexerCategories;
	[key: string]: unknown;
}

export interface CustomIndexer {
	id: number;
	name: string;
	kind: IndexerKind;
	kind_label: string;
	base_url: string;
	settings: IndexerSettings;
	// Each stored credential comes back as the mask, unset ones as an empty string.
	credentials: Record<string, string>;
	definition: Record<string, unknown> | null;
	media_types: IndexerScope[];
	enable_search: boolean;
	enable_rss: boolean;
	supports_rss: boolean;
	trust_tier: TrustTier;
	is_private: boolean;
	min_ratio: number | null;
	min_seed_minutes: number | null;
	requests_per_minute: number | null;
	min_interval_seconds: number;
	last_test_at: string | null;
	last_test_ok: boolean | null;
	last_test_message: string | null;
	health: {
		failures: number;
		last_error: string | null;
		status: IndexerHealthStatus;
	};
	site_key: string;
	created_at: string | null;
	updated_at: string | null;
}

export interface IndexerFieldSpec {
	key: string;
	label: string;
	secret: boolean;
	required: boolean;
	placeholder: string;
	help: string;
	kind: "text" | "number" | "select" | "categories";
	options: string[];
}

export interface IndexerKindInfo {
	kind: IndexerKind;
	label: string;
	description: string;
	supports_rss: boolean;
	default_categories: IndexerCategories;
	settings: IndexerFieldSpec[];
	credentials: IndexerFieldSpec[];
}

export interface IndexerTemplate {
	id: string;
	label: string;
	description: string;
	definition: Record<string, unknown>;
}

export interface IndexerWrite {
	name: string;
	kind: IndexerKind;
	base_url: string;
	settings: IndexerSettings;
	credentials: Record<string, string>;
	definition: string | null;
	media_types: IndexerScope[];
	enable_search: boolean;
	enable_rss: boolean;
	trust_tier: TrustTier;
	is_private: boolean;
	min_ratio: number | null;
	min_seed_minutes: number | null;
	requests_per_minute: number | null;
	min_interval_seconds: number;
}

export interface IndexerTestStep {
	name: string;
	ok: boolean;
	detail: string;
}

export interface IndexerTestRelease {
	title: string;
	size: number | null;
	seeders: number;
	leechers: number;
	publish_date: string | null;
	uploader: string | null;
	info_hash: string | null;
	has_download: boolean;
	detail_url: string | null;
	quality: string | null;
	category: string | null;
}

export interface IndexerTestError {
	stage: "config" | "connect" | "auth" | "rate_limit" | "http" | "parse";
	message: string;
	status: number | null;
	field: string | null;
}

export interface IndexerTestResult {
	ok: boolean;
	steps: IndexerTestStep[];
	results: IndexerTestRelease[];
	error: IndexerTestError | null;
	duration_ms: number;
}

export interface DefinitionCheckResult {
	valid: boolean;
	errors: string[];
	credentials: { key: string; label: string }[];
}

// The 422 body of a rejected save or test.
export interface IndexerValidationDetail {
	message: string;
	errors: string[];
}
