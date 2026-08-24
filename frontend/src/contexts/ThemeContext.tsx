"use client";

import {
	createContext,
	useCallback,
	useContext,
	useEffect,
	useMemo,
	useSyncExternalStore,
	ReactNode,
} from "react";
import { createLocalStorageStore } from "@/lib/localStorageStore";

type Theme = "light" | "dark";

interface ThemeContextType {
	theme: Theme;
	toggleTheme: () => void;
	setTheme: (theme: Theme) => void;
}

const ThemeContext = createContext<ThemeContextType>({
	theme: "light",
	toggleTheme: () => {},
	setTheme: () => {},
});

// Falls back to the operating system preference when nothing is stored.
const themeStore = createLocalStorageStore<Theme>({
	key: "theme",
	serverValue: "light",
	parse: (raw) => {
		if (raw === "light" || raw === "dark") return raw;
		return window.matchMedia("(prefers-color-scheme: dark)").matches
			? "dark"
			: "light";
	},
	serialize: (theme) => theme,
});

export function ThemeProvider({ children }: { children: ReactNode }) {
	const theme = useSyncExternalStore(
		themeStore.subscribe,
		themeStore.getSnapshot,
		themeStore.getServerSnapshot,
	);

	// Keeps the document class in step with the active theme.
	useEffect(() => {
		document.documentElement.classList.toggle("dark", theme === "dark");
	}, [theme]);

	const setTheme = useCallback((next: Theme) => {
		themeStore.set(next);
	}, []);

	const toggleTheme = useCallback(() => {
		themeStore.set(themeStore.getSnapshot() === "light" ? "dark" : "light");
	}, []);

	const value = useMemo(
		() => ({ theme, toggleTheme, setTheme }),
		[theme, toggleTheme, setTheme],
	);

	return (
		<ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
	);
}

export function useTheme() {
	return useContext(ThemeContext);
}
