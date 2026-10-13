import type { ToastApi, ToastOptions } from "@/components/toast/types";
import type { AppNotification } from "@/types/notifications";

// Which server notifications also appear as a toast. Anything not listed stays in the
// bell only, which covers routine events such as the VPN coming back or a port change.
const POPUP_POLICY: Record<
	string,
	{ persistent?: boolean; sound?: boolean; media?: boolean }
> = {
	// Downloads have stopped, so these stay until dismissed and play the sound.
	vpn_killswitch: { persistent: true, sound: true },
	validation_failed: { persistent: true, sound: true },
	// An automatic download is worth seeing but needs nothing, so it is quiet.
	new_download: { media: true, sound: false },
};

const MEDIA_ROUTES: Record<string, string> = {
	movie: "/movies",
	show: "/shows",
	anime: "/anime",
	album: "/music/album",
};

// Where the toast's main button goes, or null for no button.
function destination(notification: AppNotification): string | null {
	const data = notification.data ?? {};
	const mediaRoute = MEDIA_ROUTES[String(data.media_type ?? "")];
	if (mediaRoute && data.media_id != null) {
		return `${mediaRoute}/${data.media_id}`;
	}
	if (
		notification.type === "vpn_killswitch" ||
		notification.type === "validation_failed"
	) {
		return "/downloads";
	}
	return null;
}

export function showNotificationToast(
	notification: AppNotification,
	toast: ToastApi,
	navigate: (href: string) => void,
) {
	const policy = POPUP_POLICY[notification.type];
	if (!policy) return;

	const href = destination(notification);
	const poster = notification.data?.poster;
	const options: ToastOptions = {
		description: notification.message ?? undefined,
		persistent: policy.persistent,
		sound: policy.sound,
		media: policy.media
			? { poster: typeof poster === "string" ? poster : null }
			: undefined,
		actions: href
			? [{ label: "View", primary: true, onClick: () => navigate(href) }]
			: undefined,
	};
	toast.show(notification.severity, notification.title, options);
}

// Recently shown notification ids, shared by every open tab through localStorage.
const SHOWN_KEY = "kinora-shown-notifications";
const SHOWN_LIMIT = 50;
// A hidden tab waits this long before claiming, so the tab being looked at wins.
const HIDDEN_TAB_DELAY_MS = 1_500;

function claimInStorage(id: number): boolean {
	try {
		const shown: number[] = JSON.parse(
			localStorage.getItem(SHOWN_KEY) ?? "[]",
		);
		if (shown.includes(id)) return false;
		localStorage.setItem(
			SHOWN_KEY,
			JSON.stringify([...shown, id].slice(-SHOWN_LIMIT)),
		);
		return true;
	} catch {
		// Storage blocked. Showing it in every tab beats not showing it at all.
		return true;
	}
}

// Resolves true in exactly one open tab per notification. The Web Locks API makes the
// read and write of the shared list one step, so two tabs cannot both claim it.
export async function claimNotification(id: number): Promise<boolean> {
	if (document.hidden) {
		await new Promise((resolve) =>
			setTimeout(resolve, HIDDEN_TAB_DELAY_MS),
		);
	}
	if (navigator.locks) {
		return navigator.locks.request("kinora-notification-claims", () =>
			claimInStorage(id),
		);
	}
	return claimInStorage(id);
}
