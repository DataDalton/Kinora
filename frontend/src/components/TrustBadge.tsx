"use client";

import { ShieldCheck, ShieldQuestion } from "lucide-react";

const CATEGORY_LABELS: Record<string, string> = {
	kinora_list: "Kinora trusted list",
	ext_verified: "ext.to verified",
	nyaa_trusted: "Nyaa trusted",
};

const TEMPLATE_LABELS: Record<string, string> = {
	trusted: "Trusted",
	balanced: "Balanced",
	open: "Open",
};

interface TrustBadgeProps {
	trustCategory?: string | null;
	safetyTemplate?: string | null;
}

// Why a download was chosen, such as "Trusted (ext.to verified)". Shows nothing for
// downloads recorded before trust was tracked.
export default function TrustBadge({
	trustCategory,
	safetyTemplate,
}: TrustBadgeProps) {
	if (!trustCategory && !safetyTemplate) return null;
	const category = trustCategory
		? CATEGORY_LABELS[trustCategory] || trustCategory
		: "Unverified";
	const template = safetyTemplate
		? TEMPLATE_LABELS[safetyTemplate] || safetyTemplate
		: null;
	const Icon = trustCategory ? ShieldCheck : ShieldQuestion;
	return (
		<span
			className={`flex items-center gap-1 px-2 py-0.5 rounded ${
				trustCategory ? "bg-green-500/20 text-green-500" : "bg-muted"
			}`}
			title={
				template
					? `Downloaded under the ${template} template, uploader ${category}`
					: `Uploader ${category}`
			}
		>
			<Icon className="w-3 h-3" />
			{template ? `${template} (${category})` : category}
		</span>
	);
}
