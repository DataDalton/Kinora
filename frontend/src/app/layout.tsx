import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";
import { ClientLayout } from "@/components/ClientLayout";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
	title: "Kinora - Unified Media Management",
	description: "The fastest, most efficient media management platform",
	// iOS ignores the manifest icons and reads these tags when adding to the Home Screen.
	appleWebApp: {
		capable: true,
		title: "Kinora",
		statusBarStyle: "black-translucent",
	},
	icons: {
		icon: [{ url: "/icons/icon.svg", type: "image/svg+xml" }],
		apple: [{ url: "/icons/apple-touch-icon.png", sizes: "180x180" }],
	},
};

export const viewport: Viewport = {
	themeColor: "#0a0a0a",
};

export default function RootLayout({
	children,
}: {
	children: React.ReactNode;
}) {
	return (
		<html lang="en" suppressHydrationWarning>
			<body className={inter.className}>
				<Providers>
					<ClientLayout>{children}</ClientLayout>
				</Providers>
			</body>
		</html>
	);
}
