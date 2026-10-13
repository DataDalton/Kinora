import api from "../api";

// Per-user preferences. The backend fills in defaults for keys the user never set.
export interface UserPreferences {
	notificationSounds: boolean;
}

export const PREFERENCES_QUERY_KEY = ["user-preferences"];

export async function getPreferences(): Promise<UserPreferences> {
	const response = await api.get("/auth/me/preferences");
	return response.data;
}

// Sends only the fields being changed and returns the full merged preferences.
export async function updatePreferences(
	changes: Partial<UserPreferences>,
): Promise<UserPreferences> {
	const response = await api.patch("/auth/me/preferences", changes);
	return response.data;
}
