"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Copy, Eye, EyeOff, KeyRound } from "lucide-react";
import { api } from "@/lib/api";
import { useToast } from "@/components/toast/ToastProvider";
import { usePermissions } from "@/contexts/PermissionContext";

interface WebUiLogin {
	url: string;
	username: string;
	password: string;
}

// Login for the bundled qBittorrent WebUI. Kinora replaces the seeded password with a
// generated one and turns off the login bypass, so administrators read it here.
export default function QbittorrentLoginCard() {
	const { hasPermission } = usePermissions();
	const toast = useToast();
	const [revealed, setRevealed] = useState(false);
	const isAdmin = hasPermission("system.admin");

	const { data: login } = useQuery({
		queryKey: ["qbittorrent-webui-login"],
		queryFn: async () => {
			const response = await api.get("/setup/qbittorrent-webui-login");
			return response.data as WebUiLogin;
		},
		enabled: isAdmin,
		retry: false,
	});

	if (!isAdmin || !login) return null;

	const copyPassword = async () => {
		try {
			await navigator.clipboard.writeText(login.password);
			toast.success("Password copied");
		} catch {
			toast.error("Couldn't copy the password");
		}
	};

	return (
		<div className="bg-card text-card-foreground border-border border rounded-lg p-4 shadow-sm mb-4">
			<div className="flex items-center gap-2 mb-2">
				<KeyRound className="w-4 h-4 text-primary" />
				<h3 className="font-semibold text-sm">
					qBittorrent WebUI Login
				</h3>
			</div>
			<p className="text-xs text-muted-foreground mb-3">
				The bundled qBittorrent at {login.url} needs this login. Kinora
				generated the password and keeps it in sync.
			</p>
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
