"use client";

import {
	createContext,
	useCallback,
	useContext,
	useMemo,
	useSyncExternalStore,
	ReactNode,
} from "react";
import { createLocalStorageStore } from "@/lib/localStorageStore";

interface SidebarContextType {
	collapsed: boolean;
	toggleCollapsed: () => void;
}

const SidebarContext = createContext<SidebarContextType>({
	collapsed: false,
	toggleCollapsed: () => {},
});

const sidebarStore = createLocalStorageStore<boolean>({
	key: "sidebarCollapsed",
	serverValue: false,
	parse: (raw) => raw === "true",
	serialize: (collapsed) => collapsed.toString(),
});

export function SidebarProvider({ children }: { children: ReactNode }) {
	const collapsed = useSyncExternalStore(
		sidebarStore.subscribe,
		sidebarStore.getSnapshot,
		sidebarStore.getServerSnapshot,
	);

	const toggleCollapsed = useCallback(() => {
		sidebarStore.set(!sidebarStore.getSnapshot());
	}, []);

	const value = useMemo(
		() => ({ collapsed, toggleCollapsed }),
		[collapsed, toggleCollapsed],
	);

	return (
		<SidebarContext.Provider value={value}>
			{children}
		</SidebarContext.Provider>
	);
}

export function useSidebar() {
	return useContext(SidebarContext);
}
