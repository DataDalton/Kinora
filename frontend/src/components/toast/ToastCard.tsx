"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { AlertTriangle, Check, Film, Info, X } from "lucide-react";
import { createCountdown, type Countdown } from "./countdown";
import type { ToastRecord, ToastType } from "./types";

// How long each type stays on screen. Errors and warnings stay longer so there is time
// to read them, and media cards get extra time for the added detail and buttons.
const DURATION_MS: Record<ToastType, number> = {
	success: 5_000,
	info: 5_000,
	warning: 8_000,
	error: 10_000,
};
const MEDIA_EXTRA_MS = 2_000;

const TONES: Record<
	ToastType,
	{ icon: typeof Check; circle: string; badge: string; bar: string }
> = {
	success: {
		icon: Check,
		circle: "bg-green-500/15 text-green-500",
		badge: "bg-green-500 text-black",
		bar: "bg-green-500",
	},
	error: {
		icon: X,
		circle: "bg-red-500/15 text-red-400",
		badge: "bg-red-500 text-white",
		bar: "bg-red-500",
	},
	warning: {
		icon: AlertTriangle,
		circle: "bg-yellow-500/15 text-yellow-500",
		badge: "bg-yellow-500 text-black",
		bar: "bg-yellow-500",
	},
	info: {
		icon: Info,
		circle: "bg-blue-500/15 text-blue-400",
		badge: "bg-blue-500 text-white",
		bar: "bg-blue-500",
	},
};

function posterUrl(poster: string): string {
	return poster.startsWith("http")
		? poster
		: `https://image.tmdb.org/t/p/w185${poster}`;
}

function subscribeToVisibility(onChange: () => void) {
	document.addEventListener("visibilitychange", onChange);
	return () => document.removeEventListener("visibilitychange", onChange);
}

function usePageHidden() {
	return useSyncExternalStore(
		subscribeToVisibility,
		() => document.hidden,
		() => false,
	);
}

interface ToastCardProps {
	toast: ToastRecord;
	onDismiss: (id: number) => void;
}

export default function ToastCard({ toast, onDismiss }: ToastCardProps) {
	const [hovered, setHovered] = useState(false);
	const [focused, setFocused] = useState(false);
	const pageHidden = usePageHidden();
	const paused = hovered || focused || pageHidden;
	const durationMs =
		DURATION_MS[toast.type] + (toast.media ? MEDIA_EXTRA_MS : 0);
	const countdown = useRef<Countdown | null>(null);
	const tone = TONES[toast.type];
	const Icon = tone.icon;

	// A fresh countdown per renewal, so a merged duplicate restarts the full time.
	useEffect(() => {
		if (toast.persistent) return;
		const timer = createCountdown(durationMs, () => onDismiss(toast.id));
		countdown.current = timer;
		return () => {
			timer.cancel();
			countdown.current = null;
		};
	}, [toast.id, toast.persistent, toast.renewal, durationMs, onDismiss]);

	// Hover, keyboard focus inside the card, and a hidden tab all hold the countdown.
	useEffect(() => {
		const timer = countdown.current;
		if (!timer) return;
		if (paused) timer.pause();
		else timer.resume();
	}, [paused, toast.renewal]);

	const runAction = (onClick: () => void) => {
		onClick();
		onDismiss(toast.id);
	};

	const dismissButton = (
		<button
			type="button"
			onClick={() => onDismiss(toast.id)}
			aria-label="Dismiss notification"
			className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-muted-foreground transition hover:bg-accent hover:text-foreground cursor-pointer"
		>
			<X className="h-4 w-4" />
		</button>
	);

	const countBadge = toast.count > 1 && (
		<span className="shrink-0 rounded-full bg-muted px-2 py-0.5 text-xs font-semibold text-muted-foreground">
			×{toast.count}
		</span>
	);

	const actions = toast.actions && toast.actions.length > 0 && (
		<div className="mt-2.5 flex flex-wrap gap-2">
			{toast.actions.map((action) => (
				<button
					key={action.label}
					type="button"
					onClick={() => runAction(action.onClick)}
					className={`h-8 rounded-lg px-3 text-sm font-medium transition cursor-pointer ${
						action.primary
							? "bg-primary text-primary-foreground hover:opacity-90"
							: "border border-border bg-muted text-foreground hover:bg-accent"
					}`}
				>
					{action.label}
				</button>
			))}
		</div>
	);

	return (
		<div
			role={toast.type === "error" ? "alert" : "status"}
			aria-live={toast.type === "error" ? "assertive" : "polite"}
			onMouseEnter={() => setHovered(true)}
			onMouseLeave={() => setHovered(false)}
			onFocus={() => setFocused(true)}
			onBlur={(event) => {
				if (
					!event.currentTarget.contains(event.relatedTarget as Node)
				) {
					setFocused(false);
				}
			}}
			className={`pointer-events-auto relative flex gap-3 overflow-hidden rounded-xl border border-border/70 bg-card pt-3.5 pb-4 pl-3.5 pr-2.5 text-card-foreground shadow-2xl ${
				toast.leaving ? "toast-leave" : "toast-enter"
			}`}
		>
			{toast.media ? (
				<div className="relative h-19.5 w-13 shrink-0">
					{toast.media.poster ? (
						// eslint-disable-next-line @next/next/no-img-element -- remote TMDB poster at a fixed small size
						<img
							src={posterUrl(toast.media.poster)}
							alt=""
							className="h-full w-full rounded-md object-cover"
						/>
					) : (
						<div className="flex h-full w-full items-center justify-center rounded-md bg-muted text-muted-foreground">
							<Film className="h-5 w-5" aria-hidden="true" />
						</div>
					)}
					<span
						className={`absolute -right-1.5 -bottom-1.5 flex h-5.5 w-5.5 items-center justify-center rounded-full border-2 border-card ${tone.badge}`}
					>
						<Icon
							className="h-3 w-3"
							strokeWidth={3}
							aria-hidden="true"
						/>
					</span>
				</div>
			) : (
				<span
					className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${tone.circle}`}
				>
					<Icon
						className="h-4 w-4"
						strokeWidth={2.5}
						aria-hidden="true"
					/>
				</span>
			)}

			<div className={`min-w-0 flex-1 ${toast.media ? "" : "pt-1.5"}`}>
				<div className="flex items-center gap-2">
					<p className="min-w-0 flex-1 text-sm font-semibold text-foreground">
						{toast.title}
					</p>
					{countBadge}
				</div>
				{toast.media?.name && (
					<p className="mt-0.5 truncate text-sm text-foreground/90">
						{toast.media.name}
					</p>
				)}
				{toast.description && (
					<p
						className={`mt-0.5 leading-snug text-muted-foreground ${toast.media ? "text-xs" : "text-sm"}`}
					>
						{toast.description}
					</p>
				)}
				{actions}
			</div>

			<div className="-mt-1">{dismissButton}</div>

			{!toast.persistent && (
				<div
					key={toast.renewal}
					className={`absolute bottom-0 left-0 h-0.5 ${tone.bar}`}
					style={{
						animation: `toastProgress ${durationMs}ms linear forwards`,
						animationPlayState: paused ? "paused" : "running",
					}}
				/>
			)}
		</div>
	);
}
