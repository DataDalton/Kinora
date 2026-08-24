"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Activity, Inbox, Archive, Settings } from "lucide-react";
import { listImportQueue } from "@/lib/api/downloads";
import { usePermissions } from "@/contexts/PermissionContext";

const TABS = [
	{ href: "/downloads", label: "Active", icon: Activity },
	{
		href: "/downloads/import",
		label: "Import",
		icon: Inbox,
		badgeKey: "import" as const,
	},
	{ href: "/downloads/sources", label: "Sources", icon: Archive },
	{ href: "/downloads/settings", label: "Settings", icon: Settings },
];

export default function DownloadsTabs() {
	const pathname = usePathname();
	const { hasPermission } = usePermissions();
	const canManage = hasPermission("system.downloads");

	const { data: importItems } = useQuery({
		queryKey: ["import-queue"],
		queryFn: listImportQueue,
		refetchInterval: 15000,
		enabled: canManage,
	});
	const importCount = importItems?.length ?? 0;

	return (
		<div className="flex gap-1 border-b border-border">
			{TABS.map((tab) => {
				const active = pathname === tab.href;
				const badge = tab.badgeKey === "import" ? importCount : 0;
				return (
					<Link
						key={tab.href}
						href={tab.href}
						className={`relative flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 -mb-px transition ${
							active
								? "border-primary text-foreground"
								: "border-transparent text-muted-foreground hover:text-foreground hover:border-border"
						}`}
					>
						<tab.icon className="w-4 h-4" />
						{tab.label}
						{badge > 0 && (
							<span className="ml-1 bg-amber-500 text-white text-xs rounded-full h-5 min-w-5 px-1.5 flex items-center justify-center font-medium">
								{badge > 99 ? "99+" : badge}
							</span>
						)}
					</Link>
				);
			})}
		</div>
	);
}
