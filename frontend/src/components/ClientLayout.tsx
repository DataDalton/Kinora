"use client";

import { ReactNode, Suspense } from "react";
import { ThemeProvider } from "@/contexts/ThemeContext";
import { SidebarProvider, useSidebar } from "@/contexts/SidebarContext";
import { PermissionProvider } from "@/contexts/PermissionContext";
import { RealtimeProvider } from "@/contexts/RealtimeContext";
import Navigation from "@/components/Navigation";

// The login and register routes escape this margin with their own layout, so
// no route check is needed here. Reading the pathname would pull the page
// content out of the prerendered shell under Cache Components.
function MainContent({ children }: { children: ReactNode }) {
	const { collapsed } = useSidebar();

	return (
		<main
			className={`flex-1 transition-all duration-300 mt-16 md:mt-0 ${collapsed ? "md:ml-20" : "md:ml-64"}`}
		>
			{children}
		</main>
	);
}

export function ClientLayout({ children }: { children: ReactNode }) {
	return (
		<ThemeProvider>
			<PermissionProvider>
				<RealtimeProvider>
					<SidebarProvider>
						<div className="flex min-h-screen">
							<Suspense fallback={null}>
								<Navigation />
							</Suspense>
							<MainContent>{children}</MainContent>
						</div>
					</SidebarProvider>
				</RealtimeProvider>
			</PermissionProvider>
		</ThemeProvider>
	);
}
