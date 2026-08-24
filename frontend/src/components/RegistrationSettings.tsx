"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, UserPlus, Info } from "lucide-react";
import { api } from "@/lib/api";

const settingKey = "allow_user_registration";
const settingQueryKey = ["settings", settingKey];

export default function RegistrationSettings() {
	const queryClient = useQueryClient();
	const [error, setError] = useState<string | null>(null);
	const [saved, setSaved] = useState(false);

	const { data: registrationEnabled = true, isPending: loading } =
		useQuery<boolean>({
			queryKey: settingQueryKey,
			queryFn: async () => {
				try {
					const response = await api.get(`/settings/${settingKey}`);
					// The backend reads any value other than the string "false"
					// as enabled, so mirror that comparison here.
					return response.data?.value !== "false";
				} catch (err: any) {
					// A missing row predates the seed migration. The auth endpoints
					// also read that as registration being open.
					if (err.response?.status === 404) return true;
					throw new Error("Failed to load the registration setting");
				}
			},
			retry: false,
		});

	const updateMutation = useMutation({
		mutationFn: async (enabled: boolean) => {
			await api.put(`/settings/${settingKey}`, {
				value: enabled ? "true" : "false",
			});
		},
		onSuccess: () => {
			setError(null);
			setSaved(true);
			setTimeout(() => setSaved(false), 3000);
			queryClient.invalidateQueries({ queryKey: settingQueryKey });
		},
		onError: (err: any) => {
			setSaved(false);
			setError(
				err.response?.data?.detail ||
					"Failed to save the registration setting",
			);
		},
	});

	if (loading) {
		return (
			<div className="bg-card border border-border rounded-lg p-6">
				<div className="flex items-center justify-center py-8">
					<Loader2 className="w-6 h-6 animate-spin text-primary" />
				</div>
			</div>
		);
	}

	return (
		<div className="bg-card border border-border rounded-lg p-6">
			<div className="flex items-center gap-3 mb-4">
				<div className="p-2 bg-primary/10 rounded-lg">
					<UserPlus className="w-5 h-5 text-primary" />
				</div>
				<div>
					<h2 className="text-xl font-bold text-foreground">
						User Registration
					</h2>
					<p className="text-sm text-muted-foreground">
						Control whether visitors can create their own accounts
					</p>
				</div>
			</div>

			<div className="mb-6 p-4 bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-900 rounded-lg">
				<div className="flex gap-2">
					<Info className="w-5 h-5 text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5" />
					<div className="text-sm text-blue-900 dark:text-blue-100">
						<p className="font-semibold mb-1">
							What turning this off does:
						</p>
						<p>
							The register page redirects to the login page, and
							the register endpoint rejects new accounts. Existing
							users keep their accounts and can still sign in, and
							administrators can still create users from the Users
							section.
						</p>
					</div>
				</div>
			</div>

			{error && (
				<div className="mb-4 p-4 bg-destructive/10 border border-destructive/50 rounded-lg">
					<p className="text-sm text-destructive">{error}</p>
				</div>
			)}

			{saved && (
				<div className="mb-4 p-4 bg-green-100 dark:bg-green-900/30 border border-green-500 rounded-lg">
					<p className="text-sm text-green-800 dark:text-green-200">
						Settings saved successfully!
					</p>
				</div>
			)}

			<label className="flex items-center justify-between p-3 bg-muted/50 rounded-lg cursor-pointer">
				<div>
					<div className="font-semibold">Allow new registrations</div>
					<div className="text-xs text-muted-foreground">
						{registrationEnabled
							? "Anyone who can reach the login page can create an account"
							: "New account creation is closed"}
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
							checked={registrationEnabled}
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
		</div>
	);
}
