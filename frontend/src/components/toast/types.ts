export type ToastType = "success" | "error" | "warning" | "info";

export interface ToastAction {
	label: string;
	onClick: () => void;
	// The main action renders filled. Others render outlined.
	primary?: boolean;
}

// Present when the toast is about one movie, show, album or other library item. It
// switches the card to the media layout with the poster beside the text.
export interface ToastMedia {
	// TMDB poster path or full image URL. Without one the card shows a placeholder.
	poster?: string | null;
	// Item name, shown under the toast title. Omit when the title already names it.
	name?: string;
}

export interface ToastOptions {
	description?: string;
	media?: ToastMedia;
	actions?: ToastAction[];
	// Stays until dismissed instead of counting down.
	persistent?: boolean;
	// Plays the notification sound. Defaults to true for errors only.
	sound?: boolean;
}

export interface ToastRecord extends ToastOptions {
	id: number;
	type: ToastType;
	title: string;
	// Identical toasts merge into one card, and this counts how many arrived.
	count: number;
	// Increments when a duplicate merges in, restarting the countdown.
	renewal: number;
	leaving: boolean;
}

export interface ToastApi {
	show: (type: ToastType, title: string, options?: ToastOptions) => void;
	success: (title: string, options?: ToastOptions) => void;
	error: (title: string, options?: ToastOptions) => void;
	warning: (title: string, options?: ToastOptions) => void;
	info: (title: string, options?: ToastOptions) => void;
	dismiss: (id: number) => void;
}
