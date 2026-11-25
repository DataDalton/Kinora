import api from "../api";

// A browser that registered for Web Push on the current user's account.
export interface PushDevice {
	id: number;
	label: string | null;
	endpoint: string;
	enabled: boolean;
	createdAt: string;
	lastUsedAt: string | null;
}

export interface PushCategoryPreference {
	key: string;
	label: string;
	description: string;
	enabled: boolean;
}

export interface PushPreferences {
	categories: PushCategoryPreference[];
}

export interface PushTestResult {
	sent: number;
	failed: number;
	removed: number;
}

export const PUSH_DEVICES_QUERY_KEY = ["push-devices"];
export const PUSH_PREFERENCES_QUERY_KEY = ["push-preferences"];

export async function getVapidPublicKey(): Promise<string> {
	const response = await api.get("/push/vapid-public-key");
	return response.data.publicKey;
}

// Sends the PushSubscription JSON from the browser. Returns the stored device.
export async function saveSubscription(
	subscription: PushSubscriptionJSON,
	label?: string,
): Promise<PushDevice> {
	const response = await api.post("/push/subscriptions", {
		endpoint: subscription.endpoint,
		keys: subscription.keys,
		label,
	});
	return response.data;
}

export async function deleteSubscriptionByEndpoint(
	endpoint: string,
): Promise<void> {
	await api.post("/push/subscriptions/unsubscribe", { endpoint });
}

export async function listPushDevices(): Promise<PushDevice[]> {
	const response = await api.get("/push/subscriptions");
	return response.data;
}

export async function updatePushDevice(
	id: number,
	changes: { enabled?: boolean; label?: string },
): Promise<PushDevice> {
	const response = await api.patch(`/push/subscriptions/${id}`, changes);
	return response.data;
}

export async function removePushDevice(id: number): Promise<void> {
	await api.delete(`/push/subscriptions/${id}`);
}

export async function sendTestPush(deviceId?: number): Promise<PushTestResult> {
	const response = await api.post("/push/test", { deviceId });
	return response.data;
}

export async function getPushPreferences(): Promise<PushPreferences> {
	const response = await api.get("/push/preferences");
	return response.data;
}

// Sends only the categories being changed and returns every visible category.
export async function updatePushPreferences(
	types: Record<string, boolean>,
): Promise<PushPreferences> {
	const response = await api.put("/push/preferences", { types });
	return response.data;
}
