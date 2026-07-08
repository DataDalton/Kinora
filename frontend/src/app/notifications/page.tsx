"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Trash2, CheckCheck, Eraser } from "lucide-react";
import PageHeader from "@/components/PageHeader";
import {
	listNotifications,
	markNotificationRead,
	markAllNotificationsRead,
	deleteNotification,
	clearReadNotifications,
} from "@/lib/api/notifications";
import type { NotificationSeverity } from "@/types/notifications";

const SEVERITY_STYLES: Record<NotificationSeverity, string> = {
	info: "bg-blue-500",
	success: "bg-green-500",
	warning: "bg-amber-500",
	error: "bg-red-500",
};

export default function NotificationsPage() {
	const queryClient = useQueryClient();

	const { data, refetch } = useQuery({
		queryKey: ["notifications-page"],
		queryFn: () => listNotifications(false, 200),
		refetchInterval: 30000,
	});

	const refresh = () => {
		refetch();
		queryClient.invalidateQueries({ queryKey: ["notif-unread"] });
	};

	const notifications = data?.notifications ?? [];

	return (
		<div className="min-h-screen">
			<PageHeader
				title="Notifications"
				description="Download, seeding, and VPN activity"
				gradientFrom="blue-600/10"
				gradientVia="cyan-600/10"
				gradientTo="teal-600/10"
			/>

			<div className="container mx-auto px-6 py-8 max-w-3xl">
				{notifications.length > 0 && (
					<div className="flex justify-end gap-2 mb-6">
						<button
							onClick={async () => {
								await markAllNotificationsRead();
								refresh();
							}}
							className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border hover:bg-accent transition text-sm cursor-pointer"
						>
							<CheckCheck className="w-4 h-4" /> Mark all read
						</button>
						<button
							onClick={async () => {
								await clearReadNotifications();
								refresh();
							}}
							className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border hover:bg-accent transition text-sm cursor-pointer"
						>
							<Eraser className="w-4 h-4" /> Clear read
						</button>
					</div>
				)}

				{notifications.length === 0 ? (
					<div className="bg-card rounded-lg shadow p-12 text-center">
						<h2 className="text-xl font-bold mb-2">
							No notifications
						</h2>
						<p className="text-muted-foreground">
							Auto-recovery, VPN, validation, and port-change
							events appear here.
						</p>
					</div>
				) : (
					<div className="space-y-2">
						{notifications.map((n) => (
							<div
								key={n.id}
								className={`flex gap-3 bg-card text-card-foreground rounded-lg shadow p-4 ${
									n.read ? "opacity-60" : ""
								}`}
							>
								<span
									className={`w-2.5 h-2.5 rounded-full mt-1.5 flex-shrink-0 ${SEVERITY_STYLES[n.severity]}`}
								/>
								<div className="flex-1 min-w-0">
									<p className="font-medium text-sm">
										{n.title}
									</p>
									{n.message && (
										<p className="text-sm text-muted-foreground mt-0.5">
											{n.message}
										</p>
									)}
									<p className="text-xs text-muted-foreground mt-1">
										{new Date(
											n.created_at,
										).toLocaleString()}
									</p>
								</div>
								<div className="flex items-start gap-1">
									{!n.read && (
										<button
											onClick={async () => {
												await markNotificationRead(
													n.id,
												);
												refresh();
											}}
											className="p-1.5 rounded hover:bg-accent cursor-pointer"
											title="Mark read"
										>
											<Check className="w-4 h-4" />
										</button>
									)}
									<button
										onClick={async () => {
											await deleteNotification(n.id);
											refresh();
										}}
										className="p-1.5 rounded hover:bg-destructive/10 hover:text-destructive cursor-pointer"
										title="Delete"
									>
										<Trash2 className="w-4 h-4" />
									</button>
								</div>
							</div>
						))}
					</div>
				)}
			</div>
		</div>
	);
}
