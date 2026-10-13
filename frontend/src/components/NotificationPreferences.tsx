"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Loader2 } from "lucide-react";
import {
	getPreferences,
	updatePreferences,
	PREFERENCES_QUERY_KEY,
} from "@/lib/api/preferences";
import { useToast } from "@/components/toast/ToastProvider";

export default function NotificationPreferences() {
	const queryClient = useQueryClient();
	const toast = useToast();

	const { data: preferences, isPending: loading } = useQuery({
		queryKey: PREFERENCES_QUERY_KEY,
		queryFn: getPreferences,
		staleTime: Infinity,
	});

	const updateMutation = useMutation({
		mutationFn: (notificationSounds: boolean) =>
			updatePreferences({ notificationSounds }),
		onSuccess: (updated) => {
			queryClient.setQueryData(PREFERENCES_QUERY_KEY, updated);
		},
		onError: (err: any) => {
			toast.error("Couldn't save notification settings", {
				description: err.response?.data?.detail,
			});
		},
	});

	const soundsOn = preferences?.notificationSounds ?? true;

	return (
		<div className="bg-card border border-border rounded-lg p-6">
			<h2 className="text-2xl font-bold mb-6 flex items-center gap-2">
				<Bell className="w-6 h-6" />
				Notifications
			</h2>

			{loading ? (
				<div className="flex items-center justify-center py-8">
					<Loader2 className="w-6 h-6 animate-spin text-primary" />
				</div>
			) : (
				<label className="flex items-center justify-between gap-4 p-3 bg-muted/50 rounded-lg cursor-pointer">
					<div>
						<div className="font-semibold">Notification sounds</div>
						<div className="text-xs text-muted-foreground">
							{soundsOn
								? "A tone plays for errors and for alerts that need attention, such as the VPN kill switch"
								: "Notifications appear without sound"}
						</div>
					</div>
					<div className="flex items-center gap-2">
						{updateMutation.isPending && (
							<Loader2 className="w-4 h-4 animate-spin text-primary" />
						)}
						{/* The knob is positioned against this wrapper, so nothing else belongs inside it. */}
						<div className="relative inline-flex items-center">
							<input
								type="checkbox"
								checked={soundsOn}
								disabled={updateMutation.isPending}
								onChange={(e) =>
									updateMutation.mutate(e.target.checked)
								}
								className="sr-only peer"
							/>
							<div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary/20 dark:peer-focus:ring-primary/40 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-primary"></div>
						</div>
					</div>
				</label>
			)}
		</div>
	);
}
