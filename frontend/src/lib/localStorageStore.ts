"use client";

// Backs client state with localStorage and notifies subscribers when it changes.
// Components read the value through useSyncExternalStore, which returns the
// server value during hydration and the stored value afterwards. This avoids
// seeding state from inside an effect.
export function createLocalStorageStore<T>(options: {
	key: string;
	serverValue: T;
	parse: (raw: string | null) => T;
	serialize: (value: T) => string;
}) {
	const { key, serverValue, parse, serialize } = options;
	const listeners = new Set<() => void>();
	let cached: T = serverValue;
	let hasCached = false;

	const notify = () => {
		listeners.forEach((listener) => listener());
	};

	// A null key means the whole store was cleared, so drop the cache either way.
	const handleStorage = (event: StorageEvent) => {
		if (event.key !== null && event.key !== key) return;
		hasCached = false;
		notify();
	};

	return {
		subscribe(onChange: () => void) {
			if (listeners.size === 0) {
				window.addEventListener("storage", handleStorage);
			}
			listeners.add(onChange);
			return () => {
				listeners.delete(onChange);
				if (listeners.size === 0) {
					window.removeEventListener("storage", handleStorage);
				}
			};
		},
		getSnapshot(): T {
			if (!hasCached) {
				cached = parse(localStorage.getItem(key));
				hasCached = true;
			}
			return cached;
		},
		getServerSnapshot(): T {
			return serverValue;
		},
		set(value: T) {
			cached = value;
			hasCached = true;
			localStorage.setItem(key, serialize(value));
			notify();
		},
	};
}
