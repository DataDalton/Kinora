import api from "../api";
import type {
	CustomIndexer,
	DefinitionCheckResult,
	IndexerKindInfo,
	IndexerTemplate,
	IndexerTestResult,
	IndexerValidationDetail,
	IndexerWrite,
} from "../../types/indexer";

// Sent back in place of a stored credential to keep it unchanged.
export const CREDENTIAL_MASK = "********";

export async function getIndexers(): Promise<CustomIndexer[]> {
	const response = await api.get("/indexers/");
	return response.data;
}

export async function getIndexerKinds(): Promise<IndexerKindInfo[]> {
	const response = await api.get("/indexers/kinds");
	return response.data;
}

export async function getIndexerTemplates(): Promise<IndexerTemplate[]> {
	const response = await api.get("/indexers/templates");
	return response.data;
}

export async function createIndexer(
	body: IndexerWrite,
): Promise<CustomIndexer> {
	const response = await api.post("/indexers/", body);
	return response.data;
}

export async function updateIndexer(
	id: number,
	body: IndexerWrite,
): Promise<CustomIndexer> {
	const response = await api.put(`/indexers/${id}`, body);
	return response.data;
}

export async function setIndexerToggles(
	id: number,
	toggles: { enable_search?: boolean; enable_rss?: boolean },
): Promise<CustomIndexer> {
	const response = await api.patch(`/indexers/${id}/toggles`, toggles);
	return response.data;
}

export async function deleteIndexer(id: number): Promise<void> {
	await api.delete(`/indexers/${id}`);
}

export async function testIndexer(
	id: number,
	query?: string,
): Promise<IndexerTestResult> {
	const response = await api.post(`/indexers/${id}/test`, {
		query: query || null,
	});
	return response.data;
}

// Tests a configuration before it is saved. id fills masked credentials from the saved indexer.
export async function testUnsavedIndexer(
	body: IndexerWrite,
	id: number | null,
	query?: string,
): Promise<IndexerTestResult> {
	const response = await api.post("/indexers/test", {
		...body,
		id,
		query: query || null,
	});
	return response.data;
}

export async function checkDefinition(
	definition: string,
): Promise<DefinitionCheckResult> {
	const response = await api.post("/indexers/validate-definition", {
		definition,
	});
	return response.data;
}

// Every message of a rejected save or test, or the error's own message.
export function validationErrors(error: unknown): string[] {
	const detail = (
		error as { response?: { data?: { detail?: unknown } } } | undefined
	)?.response?.data?.detail;
	if (detail && typeof detail === "object" && !Array.isArray(detail)) {
		const errors = (detail as IndexerValidationDetail).errors;
		if (Array.isArray(errors) && errors.length) return errors;
	}
	if (typeof detail === "string") return [detail];
	if (Array.isArray(detail)) {
		return detail
			.map((item) => (item as { msg?: string }).msg)
			.filter((msg): msg is string => typeof msg === "string");
	}
	const message = (error as { message?: string } | undefined)?.message;
	return [message || "The request failed"];
}
