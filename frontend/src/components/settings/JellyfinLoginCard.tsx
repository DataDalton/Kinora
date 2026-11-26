"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
	CheckCircle,
	Copy,
	ExternalLink,
	Eye,
	EyeOff,
	KeyRound,
	Loader2,
	XCircle,
} from "lucide-react";
import { api } from "@/lib/api";
import { useToast } from "@/components/toast/ToastProvider";

interface JellyfinLogin {
	username: string;
	password: string;
	port: number;
}

export interface JellyfinSetupStatus {
	state: "waiting" | "linked" | "manual" | "error" | string;
	message: string;
}

// Login and linking state for the Jellyfin that docker-compose.jellyfin.yml installs. Kinora
// generated the admin password and set Jellyfin up with it, so administrators read it here.
export default function JellyfinLoginCard({
	status,
	linked,
}: {
	status: JellyfinSetupStatus | null;
	linked: boolean;
}) {
	const toast = useToast();
	const [revealed, setRevealed] = useState(false);

	const { data: login } = useQuery({
		queryKey: ["jellyfin-login"],
		queryFn: async () => {
			const response = await api.get("/settings/jellyfin/login");
			return response.data as JellyfinLogin;
		},
		retry: false,
	});

	if (!login) return null;

	// Jellyfin is published on the host Kinora is opened from.
	const jellyfinUrl =
		typeof window === "undefined"
			? `http://localhost:${login.port}`
			: `http://${window.location.hostname}:${login.port}`;

	const copyPassword = async () => {
		try {
			await navigator.clipboard.writeText(login.password);
			toast.success("Password copied");
		} catch {
			toast.error("Couldn't copy the password");
		}
	};

	const state = linked ? "linked" : (status?.state ?? "waiting");
	const stateLine =
		state === "linked"
			? {
					icon: <CheckCircle className="w-4 h-4 text-green-500" />,
					text: "Linked automatically. Library updates are on.",
				}
			: state === "manual" || state === "error"
				? {
						icon: <XCircle className="w-4 h-4 text-destructive" />,
						text: status?.message ?? "Linking did not finish",
					}
				: {
						icon: (
							<Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
						),
						text:
							status?.message ?? "Waiting for Jellyfin to start",
					};

	return (
		<div className="bg-card text-card-foreground border-border border rounded-lg p-4 shadow-sm">
			<div className="flex items-center justify-between gap-4 mb-2">
				<div className="flex items-center gap-2">
					<KeyRound className="w-4 h-4 text-primary" />
					<h3 className="font-semibold text-sm">Jellyfin Login</h3>
				</div>
				<a
					href={jellyfinUrl}
					target="_blank"
					rel="noopener noreferrer"
					className="flex items-center gap-1 text-xs text-primary hover:underline"
				>
					Open Jellyfin
					<ExternalLink className="w-3 h-3" />
				</a>
			</div>
			<p className="text-xs text-muted-foreground mb-3">
				Kinora set up the Jellyfin at {jellyfinUrl} with this admin
				login and created its API key. Each root folder is a Jellyfin
				library, and adding, moving or removing a root folder updates
				the libraries to match.
			</p>
			<div className="flex items-center gap-2 text-sm mb-3">
				{stateLine.icon}
				<span>{stateLine.text}</span>
			</div>
			<div className="flex flex-wrap items-center gap-3 text-sm">
				<span>
					<span className="text-muted-foreground">Username </span>
					<span className="font-mono">{login.username}</span>
				</span>
				<span className="flex items-center gap-2">
					<span className="text-muted-foreground">Password </span>
					<span className="font-mono">
						{revealed ? login.password : "••••••••••••"}
					</span>
					<button
						type="button"
						onClick={() => setRevealed(!revealed)}
						className="p-1.5 bg-muted rounded hover:bg-muted/80 transition cursor-pointer"
						title={revealed ? "Hide password" : "Show password"}
					>
						{revealed ? (
							<EyeOff className="w-3.5 h-3.5" />
						) : (
							<Eye className="w-3.5 h-3.5" />
						)}
					</button>
					<button
						type="button"
						onClick={copyPassword}
						className="p-1.5 bg-muted rounded hover:bg-muted/80 transition cursor-pointer"
						title="Copy password"
					>
						<Copy className="w-3.5 h-3.5" />
					</button>
				</span>
			</div>
		</div>
	);
}
