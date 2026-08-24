import api from "../api";
import type {
	MediaRequest,
	MediaRequestCreate,
	MediaRequestCount,
} from "../../types/request";

// Map API response to typed MediaRequest
function transformRequest(data: Record<string, unknown>): MediaRequest {
	return {
		id: data.id as number,
		userId: data.userId as number,
		username: data.username as string,
		mediaType: data.mediaType as MediaRequest["mediaType"],
		externalId: data.externalId as number,
		title: data.title as string,
		posterPath: data.posterPath as string | undefined,
		year: data.year as number | undefined,
		overview: data.overview as string | undefined,
		status: data.status as MediaRequest["status"],
		requestNotes: data.requestNotes as string | undefined,
		requestedAt: data.requestedAt as string,
		reviewedAt: data.reviewedAt as string | undefined,
		reviewedBy: data.reviewedBy as number | undefined,
		reviewerUsername: data.reviewerUsername as string | undefined,
		reviewNotes: data.reviewNotes as string | undefined,
		createdMediaId: data.createdMediaId as number | undefined,
	};
}

export async function getRequests(status?: string): Promise<MediaRequest[]> {
	const params = status ? { status } : {};
	const response = await api.get("/requests", { params });
	return response.data.map(transformRequest);
}

export async function getRequest(id: number): Promise<MediaRequest> {
	const response = await api.get(`/requests/${id}`);
	return transformRequest(response.data);
}

export async function createRequest(
	data: MediaRequestCreate,
): Promise<MediaRequest> {
	const response = await api.post("/requests", {
		mediaType: data.mediaType,
		externalId: data.externalId,
		title: data.title,
		posterPath: data.posterPath,
		year: data.year,
		overview: data.overview,
		requestNotes: data.requestNotes,
		mediaProfileId: data.mediaProfileId,
		rootFolderId: data.rootFolderId,
		autoSearch: data.autoSearch ?? true,
	});
	return transformRequest(response.data);
}

export async function approveRequest(
	id: number,
	notes?: string,
): Promise<MediaRequest> {
	const response = await api.post(`/requests/${id}/approve`, { notes });
	return transformRequest(response.data);
}

export async function denyRequest(
	id: number,
	notes?: string,
): Promise<MediaRequest> {
	const response = await api.post(`/requests/${id}/deny`, { notes });
	return transformRequest(response.data);
}

export async function cancelRequest(id: number): Promise<MediaRequest> {
	const response = await api.post(`/requests/${id}/cancel`);
	return transformRequest(response.data);
}

export async function getRequestCounts(): Promise<MediaRequestCount> {
	const response = await api.get("/requests/count");
	return {
		pending: response.data.pending as number,
		approved: response.data.approved as number,
		denied: response.data.denied as number,
		total: response.data.total as number,
	};
}
