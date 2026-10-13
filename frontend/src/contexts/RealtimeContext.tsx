"use client";

import {
	createContext,
	useContext,
	useEffect,
	useState,
	ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { RealtimeClient } from "@/lib/realtime";
import { useToast } from "@/components/toast/ToastProvider";
import {
	claimNotification,
	showNotificationToast,
} from "@/lib/notificationToasts";
import type { AppNotification } from "@/types/notifications";

// Resolve the realtime WebSocket URL. An explicit NEXT_PUBLIC_WS_URL wins, otherwise it
// is derived from the current page origin so it works on any domain served by the proxy
// with no rebuild. Called only on the client, where window is defined.
function resolveWsUrl(): string {
	const configured = process.env.NEXT_PUBLIC_WS_URL;
	if (configured) return configured;
	const protocol = window.location.protocol === "https:" ? "wss" : "ws";
	// The ws router is mounted under the /api/v1 prefix on the backend.
	return `${protocol}://${window.location.host}/api/v1/ws`;
}

function readToken(): string | null {
	if (typeof document === "undefined") return null;
	const row = document.cookie
		.split("; ")
		.find((r) => r.startsWith("access_token="));
	return row ? decodeURIComponent(row.split("=")[1]) : null;
}

const RealtimeContext = createContext<RealtimeClient | null>(null);

export function RealtimeProvider({ children }: { children: ReactNode }) {
	const queryClient = useQueryClient();
	const toast = useToast();
	const router = useRouter();
	const [client] = useState<RealtimeClient | null>(() =>
		typeof window !== "undefined"
			? new RealtimeClient(resolveWsUrl(), readToken)
			: null,
	);

	useEffect(() => {
		if (!client) return;

		// Refresh notification badge and lists the moment a notification arrives, and
		// raise a toast for the kinds that need attention, in one tab only.
		const unsubscribe = client.subscribe((message) => {
			if (message.type === "notification") {
				queryClient.invalidateQueries({ queryKey: ["notif-unread"] });
				queryClient.invalidateQueries({ queryKey: ["notif-list"] });
				queryClient.invalidateQueries({
					queryKey: ["notifications-page"],
				});
				const notification = message.notification as
					| AppNotification
					| undefined;
				if (notification) {
					claimNotification(notification.id).then((claimed) => {
						if (claimed) {
							showNotificationToast(notification, toast, (href) =>
								router.push(href),
							);
						}
					});
				}
			}
		});

		client.connect();
		return () => {
			unsubscribe();
			client.close();
		};
	}, [client, queryClient, toast, router]);

	return (
		<RealtimeContext.Provider value={client}>
			{children}
		</RealtimeContext.Provider>
	);
}

export function useRealtime(): RealtimeClient | null {
	return useContext(RealtimeContext);
}
