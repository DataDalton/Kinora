"use client";

import { useEffect } from "react";
import {
	type BeforeInstallPromptEvent,
	refreshExistingSubscription,
	registerServiceWorker,
	setDeferredInstallPrompt,
} from "@/lib/pwa";

function hasSessionCookie(): boolean {
	return document.cookie
		.split("; ")
		.some((row) => row.startsWith("access_token="));
}

// Registers the service worker once per page load, keeps the install prompt for the
// Install app button, and re-sends an existing push subscription for the signed-in user.
// Renders nothing.
export default function ServiceWorkerRegistrar() {
	useEffect(() => {
		const handleInstallPrompt = (event: Event) => {
			event.preventDefault();
			setDeferredInstallPrompt(event as BeforeInstallPromptEvent);
		};
		const handleInstalled = () => setDeferredInstallPrompt(null);
		window.addEventListener("beforeinstallprompt", handleInstallPrompt);
		window.addEventListener("appinstalled", handleInstalled);

		registerServiceWorker()
			.then(() =>
				hasSessionCookie() ? refreshExistingSubscription() : undefined,
			)
			.catch((err) => {
				console.warn("Service worker registration failed", err);
			});

		return () => {
			window.removeEventListener(
				"beforeinstallprompt",
				handleInstallPrompt,
			);
			window.removeEventListener("appinstalled", handleInstalled);
		};
	}, []);

	return null;
}
