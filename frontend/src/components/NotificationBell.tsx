"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Check, Trash2 } from "lucide-react";
import {
	listNotifications,
	getUnreadCount,
	markNotificationRead,
	markAllNotificationsRead,
	deleteNotification,
} from "@/lib/api/notifications";
import type { NotificationSeverity } from "@/types/notifications";

const SEVERITY_DOT: Record<NotificationSeverity, string> = {
	info: "bg-blue-500",
	success: "bg-green-500",
	warning: "bg-amber-500",
	error: "bg-red-500",
};

function timeAgo(iso: string): string {
	const diff = Date.now() - new Date(iso).getTime();
	const mins = Math.floor(diff / 60000);
	if (mins < 1) return "just now";
	if (mins < 60) return `${mins}m ago`;
	const hrs = Math.floor(mins / 60);
	if (hrs < 24) return `${hrs}h ago`;
	return `${Math.floor(hrs / 24)}d ago`;
}

export default function NotificationBell({
	collapsed,
}: {
	collapsed?: boolean;
}) {
	const queryClient = useQueryClient();
	const [open, setOpen] = useState(false);
	const ref = useRef<HTMLDivElement>(null);

	// The realtime WebSocket refreshes this instantly. The interval is a fallback
	// for when the socket is disconnected.
	const { data: unread } = useQuery({
		queryKey: ["notif-unread"],
		queryFn: getUnreadCount,
		refetchInterval: 60000,
	});

	const { data, refetch } = useQuery({
		queryKey: ["notif-list"],
		queryFn: () => listNotifications(false, 20),
		enabled: open,
	});

	useEffect(() => {
		const handler = (e: MouseEvent) => {
			if (ref.current && !ref.current.contains(e.target as Node))
				setOpen(false);
		};
		document.addEventListener("mousedown", handler);
		return () => document.removeEventListener("mousedown", handler);
	}, []);

	const refresh = () => {
		queryClient.invalidateQueries({ queryKey: ["notif-unread"] });
		refetch();
	};

	const unreadCount = unread ?? 0;
	const notifications = data?.notifications ?? [];

	const handleMarkRead = async (id: number) => {
		await markNotificationRead(id);
		refresh();
	};
	const handleMarkAll = async () => {
		await markAllNotificationsRead();
		refresh();
	};
	const handleDelete = async (id: number) => {
		await deleteNotification(id);
		refresh();
	};

	return (
		<div className="relative" ref={ref}>
			<button
				onClick={() => setOpen((o) => !o)}
				className="relative p-2 rounded-lg hover:bg-accent transition cursor-pointer"
				aria-label="Notifications"
				title="Notifications"
			>
				<Bell className="w-5 h-5" />
				{unreadCount > 0 && (
					<span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full h-4 min-w-4 px-1 flex items-center justify-center font-medium">
						{unreadCount > 9 ? "9+" : unreadCount}
					</span>
				)}
			</button>

			{open && (
				<div
					className={`absolute top-full mt-2 z-[70] w-80 max-w-[85vw] bg-card text-card-foreground rounded-lg shadow-2xl border border-border ${
						collapsed ? "left-0" : "left-0"
					}`}
				>
					<div className="flex items-center justify-between px-4 py-3 border-b border-border">
						<span className="font-semibold text-sm">
							Notifications
						</span>
						{unreadCount > 0 && (
							<button
								onClick={handleMarkAll}
								className="text-xs text-primary hover:underline cursor-pointer"
							>
								Mark all read
							</button>
						)}
					</div>

					<div className="max-h-96 overflow-y-auto">
						{notifications.length === 0 ? (
							<p className="px-4 py-8 text-center text-sm text-muted-foreground">
								No notifications
							</p>
						) : (
							notifications.map((n) => (
								<div
									key={n.id}
									className={`flex gap-2 px-4 py-3 border-b border-border/50 hover:bg-accent/40 ${
										n.read ? "opacity-60" : ""
									}`}
								>
									<span
										className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${SEVERITY_DOT[n.severity]}`}
									/>
									<div className="flex-1 min-w-0">
										<p className="text-sm font-medium">
											{n.title}
										</p>
										{n.message && (
											<p className="text-xs text-muted-foreground mt-0.5">
												{n.message}
											</p>
										)}
										<p className="text-xs text-muted-foreground mt-1">
											{timeAgo(n.created_at)}
										</p>
									</div>
									<div className="flex flex-col gap-1">
										{!n.read && (
											<button
												onClick={() =>
													handleMarkRead(n.id)
												}
												className="p-1 rounded hover:bg-accent cursor-pointer"
												title="Mark read"
											>
												<Check className="w-3.5 h-3.5" />
											</button>
										)}
										<button
											onClick={() => handleDelete(n.id)}
											className="p-1 rounded hover:bg-destructive/10 hover:text-destructive cursor-pointer"
											title="Delete"
										>
											<Trash2 className="w-3.5 h-3.5" />
										</button>
									</div>
								</div>
							))
						)}
					</div>

					<Link
						href="/notifications"
						onClick={() => setOpen(false)}
						className="block px-4 py-3 text-center text-sm text-primary hover:bg-accent/40 border-t border-border cursor-pointer"
					>
						View all
					</Link>
				</div>
			)}
		</div>
	);
}
