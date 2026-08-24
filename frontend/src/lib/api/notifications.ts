import api from "../api";
import type { NotificationsResponse } from "../../types/notifications";

export async function listNotifications(
	unreadOnly = false,
	limit = 50,
): Promise<NotificationsResponse> {
	const response = await api.get("/notifications", {
		params: { unread_only: unreadOnly, limit },
	});
	return response.data;
}

export async function getUnreadCount(): Promise<number> {
	const response = await api.get("/notifications/unread-count");
	return response.data.count;
}

export async function markNotificationRead(id: number): Promise<void> {
	await api.post(`/notifications/${id}/read`);
}

export async function markAllNotificationsRead(): Promise<void> {
	await api.post("/notifications/read-all");
}

export async function deleteNotification(id: number): Promise<void> {
	await api.delete(`/notifications/${id}`);
}

export async function clearReadNotifications(): Promise<void> {
	await api.delete("/notifications", { params: { read_only: true } });
}
