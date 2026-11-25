"use client";

import { useSyncExternalStore } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
	BellRing,
	Check,
	Download,
	Loader2,
	Send,
	Share,
	ShieldAlert,
	Smartphone,
	SquarePlus,
	Trash2,
} from "lucide-react";
import { useToast } from "@/components/toast/ToastProvider";
import {
	getPushPreferences,
	listPushDevices,
	removePushDevice,
	sendTestPush,
	updatePushDevice,
	updatePushPreferences,
	PUSH_DEVICES_QUERY_KEY,
	PUSH_PREFERENCES_QUERY_KEY,
	type PushTestResult,
} from "@/lib/api/push";
import {
	getCurrentSubscription,
	getDeferredInstallPrompt,
	isIosDevice,
	isPushSupported,
	isRunningStandalone,
	isSecureOrigin,
	promptInstall,
	subscribeThisDevice,
	subscribeToInstallPrompt,
	unsubscribeThisDevice,
} from "@/lib/pwa";

const CURRENT_DEVICE_QUERY_KEY = ["push-current-device"];

const noopSubscribe = () => () => {};

// Reads a browser-only value after hydration. The server render uses serverValue.
function useBrowserValue<T>(read: () => T, serverValue: T): T {
	return useSyncExternalStore(noopSubscribe, read, () => serverValue);
}

function errorText(err: unknown): string | undefined {
	const detail = (err as { response?: { data?: { detail?: unknown } } })
		?.response?.data?.detail;
	if (typeof detail === "string") return detail;
	return err instanceof Error ? err.message : undefined;
}

function describeTestResult(result: PushTestResult): string {
	const parts = [
		`Sent to ${result.sent} device${result.sent === 1 ? "" : "s"}`,
	];
	if (result.failed) parts.push(`${result.failed} failed`);
	if (result.removed) {
		parts.push(
			`${result.removed} expired device${result.removed === 1 ? "" : "s"} removed`,
		);
	}
	return parts.join(", ");
}

function Toggle({
	checked,
	disabled,
	onChange,
	label,
}: {
	checked: boolean;
	disabled?: boolean;
	onChange: (checked: boolean) => void;
	label: string;
}) {
	return (
		// The knob is positioned against this wrapper, so nothing else belongs inside it.
		<label className="relative inline-flex items-center cursor-pointer shrink-0">
			<input
				type="checkbox"
				aria-label={label}
				checked={checked}
				disabled={disabled}
				onChange={(e) => onChange(e.target.checked)}
				className="sr-only peer"
			/>
			<div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary/20 dark:peer-focus:ring-primary/40 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-primary"></div>
		</label>
	);
}

function InstallSection() {
	const toast = useToast();
	const installPrompt = useSyncExternalStore(
		subscribeToInstallPrompt,
		getDeferredInstallPrompt,
		() => null,
	);
	const standalone = useBrowserValue(isRunningStandalone, false);
	const ios = useBrowserValue(isIosDevice, false);

	if (standalone) {
		return (
			<div className="flex items-center gap-2 p-3 bg-muted/50 rounded-lg text-sm">
				<Check className="w-4 h-4 text-green-500 shrink-0" />
				Kinora is running as an installed app on this device
			</div>
		);
	}

	return (
		<div className="p-3 bg-muted/50 rounded-lg space-y-3">
			<div className="flex items-center justify-between gap-4">
				<div className="min-w-0">
					<div className="font-semibold">Install app</div>
					<div className="text-xs text-muted-foreground">
						Opens Kinora in its own window with a Home Screen or
						desktop icon
					</div>
				</div>
				{installPrompt && (
					<button
						type="button"
						onClick={() =>
							promptInstall().catch((err) =>
								toast.error("Couldn't start the install", {
									description: errorText(err),
								}),
							)
						}
						className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 text-sm font-medium shrink-0"
					>
						<Download className="w-4 h-4" />
						Install app
					</button>
				)}
			</div>

			{!installPrompt && ios && (
				<div className="text-sm space-y-2">
					<div className="text-muted-foreground">
						iPhone and iPad allow push notifications only from the
						installed app, on iOS 16.4 or later. In Safari:
					</div>
					<div className="flex items-center gap-2">
						<span className="font-semibold">1.</span>
						Tap <Share className="w-4 h-4 inline text-primary" />{" "}
						Share in the toolbar
					</div>
					<div className="flex items-center gap-2">
						<span className="font-semibold">2.</span>
						Choose{" "}
						<SquarePlus className="w-4 h-4 inline text-primary" />{" "}
						Add to Home Screen
					</div>
					<div className="flex items-center gap-2">
						<span className="font-semibold">3.</span>
						Open Kinora from the Home Screen and enable push below
					</div>
				</div>
			)}

			{!installPrompt && !ios && (
				<div className="text-xs text-muted-foreground">
					Use the install option in the browser&apos;s address bar or
					menu. The button appears here when the browser offers it.
				</div>
			)}
		</div>
	);
}

function InsecureContextNotice() {
	const origin = useBrowserValue(() => window.location.origin, "");
	return (
		<div className="flex items-start gap-3 p-4 bg-yellow-500/10 border border-yellow-500/50 rounded-lg">
			<ShieldAlert className="w-5 h-5 text-yellow-500 shrink-0 mt-0.5" />
			<div className="text-sm space-y-2">
				<div className="font-semibold text-yellow-500">
					Push notifications need HTTPS
				</div>
				<div>
					Browsers only allow service workers and push on a secure
					connection. Kinora is open at{" "}
					<span className="font-mono break-all">{origin}</span>, which
					is not one.
				</div>
				<div className="text-muted-foreground">
					Put Kinora behind a reverse proxy with a TLS certificate,
					such as Caddy, Traefik, or Nginx Proxy Manager, and open it
					through the https:// address. Plain http:// works only on
					localhost.
				</div>
			</div>
		</div>
	);
}

export default function PushNotificationSettings() {
	const queryClient = useQueryClient();
	const toast = useToast();

	const secure = useBrowserValue(isSecureOrigin, true);
	const supported = useBrowserValue(isPushSupported, true);
	const ios = useBrowserValue(isIosDevice, false);
	const standalone = useBrowserValue(isRunningStandalone, false);

	const { data: currentDevice } = useQuery({
		queryKey: CURRENT_DEVICE_QUERY_KEY,
		queryFn: async () => ({
			endpoint: (await getCurrentSubscription())?.endpoint ?? null,
			permission:
				typeof Notification === "undefined"
					? ("default" as NotificationPermission)
					: Notification.permission,
		}),
		enabled: secure && supported,
		staleTime: Infinity,
	});

	const { data: devices, isPending: devicesLoading } = useQuery({
		queryKey: PUSH_DEVICES_QUERY_KEY,
		queryFn: listPushDevices,
	});

	const { data: preferences, isPending: preferencesLoading } = useQuery({
		queryKey: PUSH_PREFERENCES_QUERY_KEY,
		queryFn: getPushPreferences,
		staleTime: Infinity,
	});

	const refreshDeviceState = () => {
		queryClient.invalidateQueries({ queryKey: CURRENT_DEVICE_QUERY_KEY });
		queryClient.invalidateQueries({ queryKey: PUSH_DEVICES_QUERY_KEY });
	};

	const enableMutation = useMutation({
		mutationFn: async () => {
			const device = await subscribeThisDevice();
			// A device turned off earlier stays off on re-subscribe, so turn it back on here.
			if (!device.enabled) {
				await updatePushDevice(device.id, { enabled: true });
			}
		},
		onSuccess: () => {
			toast.success("Push notifications enabled on this device");
			refreshDeviceState();
		},
		onError: (err) => {
			toast.error("Couldn't enable push notifications", {
				description: errorText(err),
			});
			refreshDeviceState();
		},
	});

	const disableMutation = useMutation({
		mutationFn: unsubscribeThisDevice,
		onSuccess: refreshDeviceState,
		onError: (err) => {
			toast.error("Couldn't turn off push on this device", {
				description: errorText(err),
			});
		},
	});

	const deviceToggleMutation = useMutation({
		mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) =>
			updatePushDevice(id, { enabled }),
		onSuccess: () =>
			queryClient.invalidateQueries({ queryKey: PUSH_DEVICES_QUERY_KEY }),
		onError: (err) => {
			toast.error("Couldn't update the device", {
				description: errorText(err),
			});
		},
	});

	const removeMutation = useMutation({
		mutationFn: removePushDevice,
		onSuccess: refreshDeviceState,
		onError: (err) => {
			toast.error("Couldn't remove the device", {
				description: errorText(err),
			});
		},
	});

	const testMutation = useMutation({
		mutationFn: (deviceId?: number) => sendTestPush(deviceId),
		onSuccess: (result) => {
			if (result.sent > 0) {
				toast.success("Test notification sent", {
					description: describeTestResult(result),
				});
			} else {
				toast.error("Test notification was not delivered", {
					description: describeTestResult(result),
				});
			}
			queryClient.invalidateQueries({ queryKey: PUSH_DEVICES_QUERY_KEY });
		},
		onError: (err) => {
			toast.error("Couldn't send a test notification", {
				description: errorText(err),
			});
		},
	});

	const preferencesMutation = useMutation({
		mutationFn: (change: Record<string, boolean>) =>
			updatePushPreferences(change),
		onSuccess: (updated) => {
			queryClient.setQueryData(PUSH_PREFERENCES_QUERY_KEY, updated);
		},
		onError: (err) => {
			toast.error("Couldn't save push settings", {
				description: errorText(err),
			});
		},
	});

	const thisEndpoint = currentDevice?.endpoint ?? null;
	const thisDeviceRegistered =
		!!thisEndpoint &&
		!!devices?.some((device) => device.endpoint === thisEndpoint);
	const permissionDenied = currentDevice?.permission === "denied";
	const iosNeedsInstall = ios && !standalone;
	const busy = enableMutation.isPending || disableMutation.isPending;

	return (
		<div className="bg-card border border-border rounded-lg p-6 space-y-6">
			<h2 className="text-2xl font-bold flex items-center gap-2">
				<Smartphone className="w-6 h-6" />
				Push notifications
			</h2>

			{!secure && <InsecureContextNotice />}

			<InstallSection />

			{secure && (
				<div className="p-3 bg-muted/50 rounded-lg space-y-3">
					<div className="flex items-center justify-between gap-4">
						<div className="min-w-0">
							<div className="font-semibold">This device</div>
							<div className="text-xs text-muted-foreground">
								{iosNeedsInstall && !supported
									? "Install Kinora to the Home Screen first. Safari only offers push to installed apps."
									: !supported
										? "This browser does not support push notifications"
										: permissionDenied
											? "Notifications are blocked for this site. Allow them in the browser's site settings, then try again."
											: thisDeviceRegistered
												? "Receives push notifications for the types chosen below"
												: "Not receiving push notifications"}
							</div>
						</div>
						{supported && (
							<div className="flex items-center gap-2 shrink-0">
								{busy && (
									<Loader2 className="w-4 h-4 animate-spin text-primary" />
								)}
								{thisDeviceRegistered ? (
									<button
										type="button"
										disabled={busy}
										onClick={() => disableMutation.mutate()}
										className="px-4 py-2 bg-secondary rounded-lg hover:bg-accent text-sm font-medium disabled:opacity-50"
									>
										Turn off
									</button>
								) : (
									<button
										type="button"
										disabled={busy || permissionDenied}
										onClick={() => enableMutation.mutate()}
										className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 text-sm font-medium disabled:opacity-50"
									>
										<BellRing className="w-4 h-4" />
										Enable push
									</button>
								)}
							</div>
						)}
					</div>
				</div>
			)}

			<div>
				<div className="flex items-center justify-between gap-4 mb-3">
					<h3 className="text-lg font-semibold">Devices</h3>
					{!!devices?.some((device) => device.enabled) && (
						<button
							type="button"
							disabled={testMutation.isPending}
							onClick={() => testMutation.mutate(undefined)}
							className="inline-flex items-center gap-2 px-3 py-1.5 bg-secondary rounded-lg hover:bg-accent text-sm font-medium disabled:opacity-50"
						>
							{testMutation.isPending ? (
								<Loader2 className="w-4 h-4 animate-spin" />
							) : (
								<Send className="w-4 h-4" />
							)}
							Test all
						</button>
					)}
				</div>
				{devicesLoading ? (
					<div className="flex items-center justify-center py-8">
						<Loader2 className="w-6 h-6 animate-spin text-primary" />
					</div>
				) : !devices?.length ? (
					<div className="text-sm text-muted-foreground">
						No devices are registered for push notifications yet
					</div>
				) : (
					<div className="space-y-2">
						{devices.map((device) => (
							<div
								key={device.id}
								className="flex items-center gap-3 p-3 bg-muted/50 rounded-lg"
							>
								<div className="min-w-0 flex-1">
									<div className="font-semibold truncate flex items-center gap-2">
										{device.label || "Unnamed device"}
										{device.endpoint === thisEndpoint && (
											<span className="text-xs px-2 py-0.5 rounded-full bg-primary/10 text-primary font-medium">
												This device
											</span>
										)}
									</div>
									<div className="text-xs text-muted-foreground">
										Added{" "}
										{new Date(
											device.createdAt,
										).toLocaleDateString()}
										{" · "}
										{device.lastUsedAt
											? `Last notified ${new Date(device.lastUsedAt).toLocaleString()}`
											: "Not notified yet"}
									</div>
								</div>
								<button
									type="button"
									title="Send a test notification"
									aria-label="Send a test notification"
									disabled={testMutation.isPending}
									onClick={() =>
										testMutation.mutate(device.id)
									}
									className="p-2 rounded-lg hover:bg-accent disabled:opacity-50"
								>
									<Send className="w-4 h-4" />
								</button>
								<button
									type="button"
									title="Remove device"
									aria-label="Remove device"
									disabled={removeMutation.isPending}
									onClick={() =>
										removeMutation.mutate(device.id)
									}
									className="p-2 rounded-lg text-destructive hover:bg-destructive/10 disabled:opacity-50"
								>
									<Trash2 className="w-4 h-4" />
								</button>
								<Toggle
									label={`Push to ${device.label || "this device"}`}
									checked={device.enabled}
									disabled={deviceToggleMutation.isPending}
									onChange={(enabled) =>
										deviceToggleMutation.mutate({
											id: device.id,
											enabled,
										})
									}
								/>
							</div>
						))}
					</div>
				)}
			</div>

			<div>
				<h3 className="text-lg font-semibold mb-3">
					Notification types
				</h3>
				{preferencesLoading ? (
					<div className="flex items-center justify-center py-8">
						<Loader2 className="w-6 h-6 animate-spin text-primary" />
					</div>
				) : (
					<div className="space-y-2">
						{preferences?.categories.map((category) => (
							<div
								key={category.key}
								className="flex items-center justify-between gap-4 p-3 bg-muted/50 rounded-lg"
							>
								<div className="min-w-0">
									<div className="font-semibold">
										{category.label}
									</div>
									<div className="text-xs text-muted-foreground">
										{category.description}
									</div>
								</div>
								<Toggle
									label={category.label}
									checked={category.enabled}
									disabled={preferencesMutation.isPending}
									onChange={(enabled) =>
										preferencesMutation.mutate({
											[category.key]: enabled,
										})
									}
								/>
							</div>
						))}
					</div>
				)}
			</div>
		</div>
	);
}
