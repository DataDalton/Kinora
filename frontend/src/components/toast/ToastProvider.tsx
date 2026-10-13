"use client";

import {
	createContext,
	useCallback,
	useContext,
	useEffect,
	useMemo,
	useRef,
	useState,
	useSyncExternalStore,
	type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import { useQuery } from "@tanstack/react-query";
import { usePermissions } from "@/contexts/PermissionContext";
import { getPreferences, PREFERENCES_QUERY_KEY } from "@/lib/api/preferences";
import { audioNotification } from "@/utils/audio";
import ToastCard from "./ToastCard";
import type { ToastApi, ToastOptions, ToastRecord, ToastType } from "./types";

// Cards on screen at once. Newer toasts push older ones into a count above the stack,
// and the older ones come back as visible cards are dismissed.
const MAX_VISIBLE = 3;
// Matches the toast-leave animation in globals.css.
const LEAVE_MS = 150;

const ToastContext = createContext<ToastApi | null>(null);

// Two toasts are the same when everything a reader sees matches, so a repeated
// action raises a count on one card instead of stacking copies.
function sameContent(
	record: ToastRecord,
	type: ToastType,
	title: string,
	options: ToastOptions,
) {
	return (
		!record.leaving &&
		record.type === type &&
		record.title === title &&
		record.description === options.description &&
		record.media?.name === options.media?.name
	);
}

const subscribeNever = () => () => {};

export function ToastProvider({ children }: { children: ReactNode }) {
	const [toasts, setToasts] = useState<ToastRecord[]>([]);
	const nextId = useRef(1);
	// The portal target only exists in the browser.
	const isClient = useSyncExternalStore(
		subscribeNever,
		() => true,
		() => false,
	);

	// Preferences need a signed-in user. Fetching earlier would 401 on the public
	// pages and send the visitor to the login page.
	const { user } = usePermissions();
	const { data: preferences } = useQuery({
		queryKey: PREFERENCES_QUERY_KEY,
		queryFn: getPreferences,
		enabled: !!user,
		staleTime: Infinity,
		retry: false,
	});
	const soundsEnabled = useRef(true);
	useEffect(() => {
		soundsEnabled.current = preferences?.notificationSounds ?? true;
	}, [preferences]);

	const dismiss = useCallback((id: number) => {
		setToasts((current) =>
			current.map((t) => (t.id === id ? { ...t, leaving: true } : t)),
		);
		setTimeout(() => {
			setToasts((current) => current.filter((t) => t.id !== id));
		}, LEAVE_MS);
	}, []);

	const show = useCallback(
		(type: ToastType, title: string, options: ToastOptions = {}) => {
			const playSound = options.sound ?? type === "error";
			if (playSound && soundsEnabled.current)
				audioNotification.play(type);

			setToasts((current) => {
				const duplicate = current.find((t) =>
					sameContent(t, type, title, options),
				);
				if (duplicate) {
					return current.map((t) =>
						t.id === duplicate.id
							? {
									...t,
									count: t.count + 1,
									renewal: t.renewal + 1,
								}
							: t,
					);
				}
				const record: ToastRecord = {
					...options,
					id: nextId.current++,
					type,
					title,
					count: 1,
					renewal: 0,
					leaving: false,
				};
				return [...current, record];
			});
		},
		[],
	);

	const api = useMemo<ToastApi>(
		() => ({
			show,
			success: (title, options) => show("success", title, options),
			error: (title, options) => show("error", title, options),
			warning: (title, options) => show("warning", title, options),
			info: (title, options) => show("info", title, options),
			dismiss,
		}),
		[show, dismiss],
	);

	const clearAll = () => {
		for (const t of toasts) dismiss(t.id);
	};

	// Newest at the bottom, nearest the corner. Hidden cards wait without counting down.
	const visible = toasts.slice(-MAX_VISIBLE);
	const waitingCount = toasts.length - visible.length;

	return (
		<ToastContext.Provider value={api}>
			{children}
			{isClient &&
				createPortal(
					<section
						aria-label="Notifications"
						className="pointer-events-none fixed right-4 bottom-4 left-4 z-100 flex flex-col gap-2.5 sm:left-auto sm:w-95"
					>
						{waitingCount > 0 && (
							<div className="pointer-events-auto flex items-center gap-2 self-end rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground shadow-lg">
								<span>+{waitingCount} more</span>
								<button
									type="button"
									onClick={clearAll}
									className="font-medium text-foreground hover:underline cursor-pointer"
								>
									Clear all
								</button>
							</div>
						)}
						{visible.map((toast) => (
							<ToastCard
								key={toast.id}
								toast={toast}
								onDismiss={dismiss}
							/>
						))}
					</section>,
					document.body,
				)}
		</ToastContext.Provider>
	);
}

export function useToast(): ToastApi {
	const context = useContext(ToastContext);
	if (!context) {
		throw new Error("useToast must be used inside ToastProvider");
	}
	return context;
}
