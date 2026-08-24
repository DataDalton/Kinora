// WebSocket client for server-pushed realtime messages. Reconnects with
// exponential backoff and keeps the connection alive with periodic pings.
// Consumers register a handler with subscribe() to receive parsed messages.

export interface RealtimeMessage {
	type?: string;
	[key: string]: unknown;
}

type MessageHandler = (message: RealtimeMessage) => void;

const PING_INTERVAL_MS = 25000;
const MAX_BACKOFF_MS = 30000;

export class RealtimeClient {
	private baseUrl: string;
	private getToken: () => string | null;
	private ws: WebSocket | null = null;
	private handlers = new Set<MessageHandler>();
	private reconnectAttempts = 0;
	private pingTimer: ReturnType<typeof setInterval> | null = null;
	private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
	private closed = false;

	constructor(baseUrl: string, getToken: () => string | null) {
		this.baseUrl = baseUrl.replace(/\/$/, "");
		this.getToken = getToken;
	}

	connect(): void {
		this.closed = false;
		this.open();
	}

	subscribe(handler: MessageHandler): () => void {
		this.handlers.add(handler);
		return () => {
			this.handlers.delete(handler);
		};
	}

	close(): void {
		this.closed = true;
		this.clearTimers();
		if (this.ws) {
			this.ws.onopen = null;
			this.ws.onmessage = null;
			this.ws.onclose = null;
			this.ws.onerror = null;
			try {
				this.ws.close();
			} catch {
				// ignore
			}
			this.ws = null;
		}
		this.handlers.clear();
	}

	private open(): void {
		if (this.closed) return;
		const token = this.getToken();
		if (!token) {
			// Retry when no auth token is available.
			this.scheduleReconnect();
			return;
		}

		let socket: WebSocket;
		try {
			socket = new WebSocket(
				`${this.baseUrl}/stream?token=${encodeURIComponent(token)}`,
			);
		} catch {
			this.scheduleReconnect();
			return;
		}
		this.ws = socket;

		socket.onopen = () => {
			this.reconnectAttempts = 0;
			this.startPing();
		};

		socket.onmessage = (event) => {
			if (event.data === "pong") return;
			let message: RealtimeMessage;
			try {
				message = JSON.parse(event.data as string);
			} catch {
				return;
			}
			this.handlers.forEach((handler) => {
				try {
					handler(message);
				} catch {
					// One failing handler must not block the others.
				}
			});
		};

		socket.onclose = () => {
			this.stopPing();
			if (!this.closed) this.scheduleReconnect();
		};

		socket.onerror = () => {
			// Close the socket so the close handler runs the reconnect.
			try {
				socket.close();
			} catch {
				// ignore
			}
		};
	}

	private startPing(): void {
		this.stopPing();
		this.pingTimer = setInterval(() => {
			if (this.ws && this.ws.readyState === WebSocket.OPEN) {
				this.ws.send("ping");
			}
		}, PING_INTERVAL_MS);
	}

	private stopPing(): void {
		if (this.pingTimer) {
			clearInterval(this.pingTimer);
			this.pingTimer = null;
		}
	}

	private scheduleReconnect(): void {
		if (this.closed || this.reconnectTimer) return;
		const delay = Math.min(
			MAX_BACKOFF_MS,
			1000 * 2 ** this.reconnectAttempts,
		);
		this.reconnectAttempts += 1;
		this.reconnectTimer = setTimeout(() => {
			this.reconnectTimer = null;
			this.open();
		}, delay);
	}

	private clearTimers(): void {
		this.stopPing();
		if (this.reconnectTimer) {
			clearTimeout(this.reconnectTimer);
			this.reconnectTimer = null;
		}
	}
}
