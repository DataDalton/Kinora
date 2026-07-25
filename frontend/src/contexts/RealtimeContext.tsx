"use client";

import {
	createContext,
	useContext,
	useEffect,
	useState,
	ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { RealtimeClient } from "@/lib/realtime";

// Resolve the realtime WebSocket URL. An explicit NEXT_PUBLIC_WS_URL wins, otherwise it
// is derived from the current page origin so it works on any domain served by the proxy
// with no rebuild. Called only on the client, where window is defined.
function resolveWsUrl(): string {
	const configured = process.env.NEXT_PUBLIC_WS_URL;
	if (configured) return configured;
	const protocol = window.location.protocol === "https:" ? "wss" : "ws";
	return `${protocol}://${window.location.host}/ws`;
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
	const [client] = useState<RealtimeClient | null>(() =>
		typeof window !== "undefined"
			? new RealtimeClient(resolveWsUrl(), readToken)
			: null,
	);

	useEffect(() => {
		if (!client) return;

		// Refresh notification badge and lists the moment a notification arrives.
		const unsubscribe = client.subscribe((message) => {
			if (message.type === "notification") {
				queryClient.invalidateQueries({ queryKey: ["notif-unread"] });
				queryClient.invalidateQueries({ queryKey: ["notif-list"] });
				queryClient.invalidateQueries({
					queryKey: ["notifications-page"],
				});
			}
		});

		client.connect();
		return () => {
			unsubscribe();
			client.close();
		};
	}, [client, queryClient]);

	return (
		<RealtimeContext.Provider value={client}>
			{children}
		</RealtimeContext.Provider>
	);
}

export function useRealtime(): RealtimeClient | null {
	return useContext(RealtimeContext);
}
