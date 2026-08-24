"use client";

import React, {
	createContext,
	useCallback,
	useContext,
	useMemo,
	useSyncExternalStore,
	ReactNode,
} from "react";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { useIsHydrated } from "@/lib/useIsHydrated";

interface PermissionGroup {
	id: number;
	name: string;
	displayName: string;
	color?: string;
}

interface UserInfo {
	id: number;
	username: string;
	groups: PermissionGroup[];
}

interface AuthMeResponse {
	id: number;
	username: string;
	permissions?: string[];
	groups?: PermissionGroup[];
}

interface PermissionContextType {
	permissions: Set<string>;
	groups: PermissionGroup[];
	user: UserInfo | null;
	loading: boolean;
	hasPermission: (permission: string) => boolean;
	hasAnyPermission: (...permissions: string[]) => boolean;
	hasAllPermissions: (...permissions: string[]) => boolean;
	canView: (mediaType: string) => boolean;
	canManage: (mediaType: string) => boolean;
	canRequest: (mediaType: string) => boolean;
	canApprove: (mediaType: string) => boolean;
	canDownload: (mediaType: string) => boolean;
	isAdmin: boolean;
	refreshPermissions: () => Promise<void>;
}

const PermissionContext = createContext<PermissionContextType | null>(null);

// The access token cookie is an external store. Reading it through
// useSyncExternalStore keeps the token out of an effect and lets the login
// event re-read it, which in turn enables the permissions query.
const tokenListeners = new Set<() => void>();
let cachedSnapshot = "0:0";
let hasReadToken = false;
// Bumped on every login so signing in again on a live session refetches,
// which the previous effect did unconditionally.
let authEpoch = 0;

const readHasToken = () =>
	document.cookie.split("; ").some((row) => row.startsWith("access_token="));

const handleAuthLogin = () => {
	hasReadToken = false;
	authEpoch += 1;
	tokenListeners.forEach((listener) => listener());
};

const subscribeToToken = (onChange: () => void) => {
	if (tokenListeners.size === 0) {
		window.addEventListener("auth:login", handleAuthLogin);
	}
	tokenListeners.add(onChange);
	return () => {
		tokenListeners.delete(onChange);
		if (tokenListeners.size === 0) {
			window.removeEventListener("auth:login", handleAuthLogin);
		}
	};
};

// Encoded as "<hasToken>:<epoch>" so the value stays a stable primitive.
const getTokenSnapshot = () => {
	if (!hasReadToken) {
		cachedSnapshot = `${readHasToken() ? 1 : 0}:${authEpoch}`;
		hasReadToken = true;
	}
	return cachedSnapshot;
};

const getServerTokenSnapshot = () => "0:0";

const emptyPermissions: Set<string> = new Set();
const emptyGroups: PermissionGroup[] = [];

export function PermissionProvider({ children }: { children: ReactNode }) {
	const hydrated = useIsHydrated();
	const tokenSnapshot = useSyncExternalStore(
		subscribeToToken,
		getTokenSnapshot,
		getServerTokenSnapshot,
	);
	const hasToken = tokenSnapshot.startsWith("1:");

	const { data, isPending, refetch } = useQuery<AuthMeResponse>({
		queryKey: ["auth", "me", tokenSnapshot],
		queryFn: async () => {
			try {
				const response = await api.get("/auth/me");
				return response.data;
			} catch (error) {
				console.error("Failed to fetch permissions:", error);
				throw error;
			}
		},
		enabled: hasToken,
		retry: false,
	});

	// Without a token there is nothing to load. Before hydration the token is
	// unknown, so callers keep waiting rather than seeing an empty permission set.
	const loading = !hydrated || (hasToken && isPending);

	const permissions = useMemo(
		() =>
			data?.permissions ? new Set(data.permissions) : emptyPermissions,
		[data],
	);
	const groups = data?.groups ?? emptyGroups;
	const user = useMemo<UserInfo | null>(
		() =>
			data
				? {
						id: data.id,
						username: data.username,
						groups: data.groups || [],
					}
				: null,
		[data],
	);

	const refreshPermissions = useCallback(async () => {
		await refetch();
	}, [refetch]);

	const hasPermission = useCallback(
		(permission: string) => permissions.has(permission),
		[permissions],
	);

	const hasAnyPermission = useCallback(
		(...perms: string[]) => perms.some((p) => permissions.has(p)),
		[permissions],
	);

	const hasAllPermissions = useCallback(
		(...perms: string[]) => perms.every((p) => permissions.has(p)),
		[permissions],
	);

	// Media-specific helpers matching our permission system
	const canView = useCallback(
		(mediaType: string) => hasPermission(`${mediaType}.view`),
		[hasPermission],
	);
	const canManage = useCallback(
		(mediaType: string) => hasPermission(`${mediaType}.manage`),
		[hasPermission],
	);
	const canRequest = useCallback(
		(mediaType: string) => hasPermission(`${mediaType}.request`),
		[hasPermission],
	);
	const canApprove = useCallback(
		(mediaType: string) => hasPermission(`${mediaType}.approve`),
		[hasPermission],
	);
	const canDownload = useCallback(
		(mediaType: string) => hasPermission(`${mediaType}.download`),
		[hasPermission],
	);

	const isAdmin = hasPermission("system.admin");

	const value = useMemo<PermissionContextType>(
		() => ({
			permissions,
			groups,
			user,
			loading,
			hasPermission,
			hasAnyPermission,
			hasAllPermissions,
			canView,
			canManage,
			canRequest,
			canApprove,
			canDownload,
			isAdmin,
			refreshPermissions,
		}),
		[
			permissions,
			groups,
			user,
			loading,
			hasPermission,
			hasAnyPermission,
			hasAllPermissions,
			canView,
			canManage,
			canRequest,
			canApprove,
			canDownload,
			isAdmin,
			refreshPermissions,
		],
	);

	return (
		<PermissionContext.Provider value={value}>
			{children}
		</PermissionContext.Provider>
	);
}

export function usePermissions() {
	const context = useContext(PermissionContext);
	if (!context) {
		throw new Error(
			"usePermissions must be used within a PermissionProvider",
		);
	}
	return context;
}

// Helper component for conditional rendering
interface RequirePermissionProps {
	permission: string | string[];
	mode?: "any" | "all";
	children: ReactNode;
	fallback?: ReactNode;
}

export function RequirePermission({
	permission,
	mode = "any",
	children,
	fallback = null,
}: RequirePermissionProps) {
	const { hasPermission, hasAnyPermission, hasAllPermissions, loading } =
		usePermissions();

	if (loading) return null;

	const perms = Array.isArray(permission) ? permission : [permission];
	const hasAccess =
		mode === "all"
			? hasAllPermissions(...perms)
			: hasAnyPermission(...perms);

	return hasAccess ? <>{children}</> : <>{fallback}</>;
}
