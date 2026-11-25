// Kinora service worker. Shows Web Push notifications and routes clicks back into the app.

const defaultIcon = "/icons/icon-192.png";
const badgeIcon = "/icons/badge-96.png";

self.addEventListener("install", () => {
	self.skipWaiting();
});

// Take control of open pages right away so notificationclick can navigate them.
self.addEventListener("activate", (event) => {
	event.waitUntil(self.clients.claim());
});

function readPayload(event) {
	if (!event.data) {
		return {};
	}
	try {
		return event.data.json();
	} catch {
		return { body: event.data.text() };
	}
}

self.addEventListener("push", (event) => {
	const payload = readPayload(event);
	const title = payload.title || "Kinora";
	const options = {
		body: payload.body || "",
		icon: payload.icon || defaultIcon,
		badge: badgeIcon,
		data: { url: payload.url || "/notifications" },
	};
	// A shared tag replaces an earlier notification for the same item instead of stacking.
	if (payload.tag) {
		options.tag = payload.tag;
		options.renotify = true;
	}
	event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
	event.notification.close();
	const target = new URL(
		event.notification.data?.url || "/",
		self.location.origin,
	).href;

	event.waitUntil(
		(async () => {
			const windows = await self.clients.matchAll({
				type: "window",
				includeUncontrolled: true,
			});
			const existing = windows.find(
				(client) => new URL(client.url).origin === self.location.origin,
			);
			if (existing) {
				await existing.focus();
				if (existing.url !== target && "navigate" in existing) {
					try {
						await existing.navigate(target);
					} catch {
						// navigate rejects for a page this worker does not control yet.
						await self.clients.openWindow(target);
					}
				}
				return;
			}
			await self.clients.openWindow(target);
		})(),
	);
});
