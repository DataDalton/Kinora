import { Loader2 } from "lucide-react";

// Fallback for route level Suspense boundaries created by loading.tsx.
export default function RouteLoading() {
	return (
		<div className="flex min-h-[60vh] items-center justify-center">
			<Loader2 className="w-8 h-8 animate-spin text-primary" />
		</div>
	);
}
