import { ReactNode } from "react";

// Covers the app chrome so the form is centred in the viewport rather than in
// the sidebar-offset main area. Keeps the parent layout free of route checks.
export default function AuthLayout({ children }: { children: ReactNode }) {
	return (
		<div className="fixed inset-0 z-40 overflow-auto bg-background">
			{children}
		</div>
	);
}
