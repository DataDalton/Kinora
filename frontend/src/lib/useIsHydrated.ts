"use client";

import { useSyncExternalStore } from "react";

const subscribe = () => () => {};
const getSnapshot = () => true;
const getServerSnapshot = () => false;

// Returns false during the server render and hydration, then true. Use it for
// markup that can only be produced on the client, instead of flipping a
// mounted flag from inside an effect.
export function useIsHydrated() {
	return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
