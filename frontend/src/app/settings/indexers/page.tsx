"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import PageHeader from "@/components/PageHeader";
import IndexersSection from "@/components/settings/indexers/IndexersSection";

// Standalone page for the user-defined indexers, matching the other settings pages.
export default function IndexersSettingsPage() {
	return (
		<div className="min-h-screen bg-background">
			<PageHeader
				title="Indexers"
				description="Private trackers and other sites searched directly by Kinora"
				gradientFrom="violet-600/10"
				gradientVia="purple-600/10"
				gradientTo="fuchsia-600/10"
			>
				<Link
					href="/settings"
					className="flex items-center gap-1 px-3 py-1.5 text-sm rounded bg-muted hover:bg-muted/80 transition cursor-pointer"
				>
					<ArrowLeft className="w-4 h-4" />
					Settings
				</Link>
			</PageHeader>
			<IndexersSection showHeader={false} />
		</div>
	);
}
