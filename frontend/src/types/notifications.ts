export type NotificationSeverity = "info" | "success" | "warning" | "error";

export interface AppNotification {
	id: number;
	type: string;
	severity: NotificationSeverity;
	title: string;
	message: string | null;
	data: Record<string, unknown> | null;
	read: boolean;
	created_at: string;
}

export interface NotificationsResponse {
	notifications: AppNotification[];
	total: number;
	unread: number;
}
