"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
	ShieldCheck,
	ShieldAlert,
	ShieldX,
	RefreshCw,
	Power,
	Plug,
	Lock,
	Unlock,
} from "lucide-react";
import {
	getConnectionSafety,
	getGluetunStatus,
	gluetunControl,
	gluetunSyncPort,
} from "@/lib/api/downloads";

interface Props {
	canControl: boolean;
	notify: (message: string, type?: "success" | "error") => void;
}

const SEVERITY_STYLES: Record<string, string> = {
	ok: "bg-green-500/10 border-green-500/30 text-green-600",
	warn: "bg-amber-500/10 border-amber-500/30 text-amber-600",
	error: "bg-red-500/10 border-red-500/30 text-red-600",
};

export default function ConnectionSafetyBanner({ canControl, notify }: Props) {
	const [busy, setBusy] = useState(false);

	const { data: safety, refetch: refetchSafety } = useQuery({
		queryKey: ["connection-safety"],
		queryFn: getConnectionSafety,
		refetchInterval: 15000,
	});

	const { data: gluetun, refetch: refetchGluetun } = useQuery({
		queryKey: ["gluetun-status"],
		queryFn: getGluetunStatus,
		refetchInterval: 15000,
	});

	if (!safety) return null;

	const severity = safety.severity || "warn";
	const Icon =
		severity === "ok"
			? ShieldCheck
			: severity === "error"
				? ShieldX
				: ShieldAlert;

	const runControl = async (fn: () => Promise<unknown>, msg: string) => {
		if (busy) return;
		setBusy(true);
		try {
			await fn();
			notify(msg, "success");
			refetchSafety();
			refetchGluetun();
		} catch (err: unknown) {
			notify(
				err instanceof Error ? err.message : "Action failed",
				"error",
			);
		} finally {
			setBusy(false);
		}
	};

	return (
		<div
			className={`rounded-lg border p-4 mb-6 ${SEVERITY_STYLES[severity]}`}
		>
			<div className="flex items-start justify-between gap-4 flex-wrap">
				<div className="flex items-start gap-3">
					<Icon className="w-5 h-5 mt-0.5 flex-shrink-0" />
					<div>
						<p className="font-medium text-sm">{safety.message}</p>
						<div className="flex gap-4 text-xs mt-1 flex-wrap text-foreground/70">
							{safety.client_public_ip && (
								<span>Exit IP: {safety.client_public_ip}</span>
							)}
							{safety.country && (
								<span>
									{safety.city ? `${safety.city}, ` : ""}
									{safety.country}
								</span>
							)}
							{safety.provider && <span>{safety.provider}</span>}
							{typeof safety.forwarded_port === "number" &&
								safety.forwarded_port > 0 && (
									<span>
										Forwarded port: {safety.forwarded_port}
									</span>
								)}
						</div>
						{safety.kinora_public_ip && (
							<div className="text-xs mt-1 text-foreground/70">
								Kinora IP: {safety.kinora_public_ip}
							</div>
						)}
						{typeof safety.interface_bound === "boolean" && (
							<div className="mt-1.5 text-xs">
								{safety.interface_bound ? (
									<span className="inline-flex items-center gap-1 text-green-600 dark:text-green-400 font-medium">
										<Lock className="w-3.5 h-3.5" />
										qBittorrent bound to{" "}
										{safety.client_interface ||
											"the VPN interface"}
									</span>
								) : (
									<span className="inline-flex items-center gap-1 text-amber-600 dark:text-amber-400 font-medium">
										<Unlock className="w-3.5 h-3.5" />
										qBittorrent is not interface-bound
										(protected by the VPN kill switch only)
									</span>
								)}
							</div>
						)}
					</div>
				</div>

				{canControl && gluetun?.configured && (
					<div className="flex gap-2 flex-wrap">
						<button
							onClick={() =>
								runControl(
									() => gluetunControl("restart"),
									"Reconnecting VPN",
								)
							}
							disabled={busy}
							className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-current/30 hover:bg-current/10 text-xs cursor-pointer disabled:opacity-50"
						>
							<RefreshCw className="w-3.5 h-3.5" /> Reconnect
						</button>
						<button
							onClick={() =>
								runControl(
									() =>
										gluetunControl(
											gluetun.running ? "stop" : "start",
										),
									gluetun.running
										? "Stopping VPN"
										: "Starting VPN",
								)
							}
							disabled={busy}
							className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-current/30 hover:bg-current/10 text-xs cursor-pointer disabled:opacity-50"
						>
							<Power className="w-3.5 h-3.5" />{" "}
							{gluetun.running ? "Stop" : "Start"}
						</button>
						<button
							onClick={() =>
								runControl(
									gluetunSyncPort,
									"Synced forwarded port",
								)
							}
							disabled={busy}
							className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-current/30 hover:bg-current/10 text-xs cursor-pointer disabled:opacity-50"
						>
							<Plug className="w-3.5 h-3.5" /> Sync port
						</button>
					</div>
				)}
			</div>
		</div>
	);
}
