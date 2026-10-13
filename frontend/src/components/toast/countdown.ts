// A timer that can be paused and resumed without losing the time already elapsed.
// It lives outside React so the clock reads happen in plain functions rather than
// in component code.
export interface Countdown {
	resume: () => void;
	pause: () => void;
	cancel: () => void;
}

export function createCountdown(
	durationMs: number,
	onDone: () => void,
): Countdown {
	let remainingMs = durationMs;
	let startedAt = 0;
	let timer: ReturnType<typeof setTimeout> | null = null;

	return {
		resume() {
			if (timer !== null || remainingMs <= 0) return;
			startedAt = performance.now();
			timer = setTimeout(() => {
				timer = null;
				remainingMs = 0;
				onDone();
			}, remainingMs);
		},
		pause() {
			if (timer === null) return;
			clearTimeout(timer);
			timer = null;
			remainingMs -= performance.now() - startedAt;
		},
		cancel() {
			if (timer !== null) clearTimeout(timer);
			timer = null;
		},
	};
}
