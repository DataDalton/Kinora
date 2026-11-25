// Browser side of the installable app and Web Push. Every function checks for the APIs
// it needs, since Safari outside an installed app has no PushManager.

import {
	deleteSubscriptionByEndpoint,
	getVapidPublicKey,
	saveSubscription,
	type PushDevice,
} from "@/lib/api/push";

export const SERVICE_WORKER_URL = "/sw.js";

// The event Chromium browsers fire when the app meets the install criteria.
export interface BeforeInstallPromptEvent extends Event {
	prompt: () => Promise<void>;
	userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

export function isPushSupported(): boolean {
	return (
		typeof window !== "undefined" &&
		"serviceWorker" in navigator &&
		"PushManager" in window &&
		"Notification" in window
	);
}

export function isSecureOrigin(): boolean {
	return typeof window !== "undefined" && window.isSecureContext;
}

// iPadOS reports itself as macOS, so a touch-capable Mac is treated as an iPad.
export function isIosDevice(): boolean {
	if (typeof navigator === "undefined") return false;
	const ua = navigator.userAgent;
	return (
		/iPhone|iPad|iPod/.test(ua) ||
		(ua.includes("Macintosh") && navigator.maxTouchPoints > 1)
	);
}

export function isRunningStandalone(): boolean {
	if (typeof window === "undefined") return false;
	return (
		window.matchMedia("(display-mode: standalone)").matches ||
		(navigator as Navigator & { standalone?: boolean }).standalone === true
	);
}

function base64UrlToBytes(value: string): Uint8Array<ArrayBuffer> {
	const padded = value + "=".repeat((4 - (value.length % 4)) % 4);
	const binary = atob(padded.replace(/-/g, "+").replace(/_/g, "/"));
	const bytes = new Uint8Array(new ArrayBuffer(binary.length));
	for (let i = 0; i < binary.length; i++) {
		bytes[i] = binary.charCodeAt(i);
	}
	return bytes;
}

export async function registerServiceWorker(): Promise<ServiceWorkerRegistration | null> {
	if (!isSecureOrigin() || !("serviceWorker" in navigator)) return null;
	return navigator.serviceWorker.register(SERVICE_WORKER_URL, {
		scope: "/",
		updateViaCache: "none",
	});
}

export async function getCurrentSubscription(): Promise<PushSubscription | null> {
	if (!isPushSupported() || !isSecureOrigin()) return null;
	const registration = await navigator.serviceWorker.getRegistration("/");
	if (!registration) return null;
	return registration.pushManager.getSubscription();
}

// Asks for notification permission, subscribes this browser, and stores the
// subscription on the server. Must run from a click so browsers show the prompt.
export async function subscribeThisDevice(): Promise<PushDevice> {
	if (!isSecureOrigin()) {
		throw new Error(
			"Push notifications need Kinora to be opened over HTTPS",
		);
	}
	if (!isPushSupported()) {
		throw new Error("This browser does not support push notifications");
	}

	const permission = await Notification.requestPermission();
	if (permission !== "granted") {
		throw new Error(
			permission === "denied"
				? "Notifications are blocked for this site in the browser settings"
				: "Notification permission was not granted",
		);
	}

	const registration =
		(await navigator.serviceWorker.getRegistration("/")) ??
		(await registerServiceWorker());
	if (!registration) {
		throw new Error("The service worker could not be registered");
	}
	await navigator.serviceWorker.ready;

	const publicKey = await getVapidPublicKey();
	let subscription = await registration.pushManager.getSubscription();
	// A subscription made with a different VAPID key cannot receive this server's pushes.
	if (subscription) {
		const currentKey = subscription.options.applicationServerKey;
		const expectedKey = base64UrlToBytes(publicKey);
		const sameKey =
			currentKey &&
			new Uint8Array(currentKey).every(
				(byte, i) => byte === expectedKey[i],
			);
		if (!sameKey) {
			await subscription.unsubscribe();
			subscription = null;
		}
	}
	subscription ??= await registration.pushManager.subscribe({
		userVisibleOnly: true,
		applicationServerKey: base64UrlToBytes(publicKey),
	});

	return saveSubscription(subscription.toJSON());
}

// Unsubscribes this browser and removes its row on the server.
export async function unsubscribeThisDevice(): Promise<void> {
	const subscription = await getCurrentSubscription();
	if (!subscription) return;
	const endpoint = subscription.endpoint;
	await subscription.unsubscribe();
	await deleteSubscriptionByEndpoint(endpoint);
}

// Re-sends an existing subscription so the server has current keys and the right
// account after a different user signs in on this browser.
export async function refreshExistingSubscription(): Promise<void> {
	if (typeof Notification === "undefined") return;
	if (Notification.permission !== "granted") return;
	const subscription = await getCurrentSubscription();
	if (subscription) {
		await saveSubscription(subscription.toJSON());
	}
}

// Holds the deferred install prompt so any component can offer installation after the
// event has already fired.
let deferredInstallPrompt: BeforeInstallPromptEvent | null = null;
const installPromptListeners = new Set<() => void>();

function notifyInstallPromptListeners() {
	installPromptListeners.forEach((listener) => listener());
}

export function setDeferredInstallPrompt(
	event: BeforeInstallPromptEvent | null,
) {
	deferredInstallPrompt = event;
	notifyInstallPromptListeners();
}

export function getDeferredInstallPrompt(): BeforeInstallPromptEvent | null {
	return deferredInstallPrompt;
}

export function subscribeToInstallPrompt(listener: () => void): () => void {
	installPromptListeners.add(listener);
	return () => installPromptListeners.delete(listener);
}

export async function promptInstall(): Promise<boolean> {
	const event = deferredInstallPrompt;
	if (!event) return false;
	await event.prompt();
	const choice = await event.userChoice;
	// A prompt event can be used once, so it is cleared whatever the outcome.
	setDeferredInstallPrompt(null);
	return choice.outcome === "accepted";
}
