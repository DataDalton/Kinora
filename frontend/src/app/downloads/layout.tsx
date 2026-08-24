import PageHeader from "@/components/PageHeader";
import DownloadsTabs from "./components/DownloadsTabs";

export default function DownloadsLayout({
	children,
}: {
	children: React.ReactNode;
}) {
	return (
		<div className="min-h-screen">
			<PageHeader
				title="Downloads"
				description="Live download client monitoring, seeding, and control"
				gradientFrom="blue-600/10"
				gradientVia="cyan-600/10"
				gradientTo="teal-600/10"
			/>
			<div className="container mx-auto px-6 pt-4">
				<DownloadsTabs />
			</div>
			{children}
		</div>
	);
}
