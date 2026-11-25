"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
	AlertTriangle,
	ShieldCheck,
	ShieldHalf,
	ShieldOff,
} from "lucide-react";
import { api } from "@/lib/api";
import { MediaProfileFormData, SafetyTemplate } from "../types";

interface TemplateSite {
	key: string;
	name: string;
	tier: "balanced" | "open";
}

interface UploaderCategory {
	key: string | null;
	name: string;
	trusted: boolean;
}

interface TemplateDescription {
	sources: TemplateSite[];
	uploader_categories: UploaderCategory[];
}

interface TrustedUploader {
	id: number;
	display_name: string;
	ext_name: string | null;
	leetx_name: string | null;
	enabled: boolean;
}

const TEMPLATES: {
	value: SafetyTemplate;
	label: string;
	description: string;
	icon: typeof ShieldCheck;
}[] = [
	{
		value: "trusted",
		label: "Trusted",
		description:
			"Only uploaders in a trusted category, on any site. The safest choice and the default for new profiles.",
		icon: ShieldCheck,
	},
	{
		value: "balanced",
		label: "Balanced",
		description:
			"Trusted uploaders anywhere, plus any uploader on 1337x, YTS or Nyaa.",
		icon: ShieldHalf,
	},
	{
		value: "open",
		label: "Open",
		description:
			"Every release from every site, including EZTV, RARBG, ThePirateBay, UIndex and DHT.",
		icon: ShieldOff,
	},
];

interface SafetyTemplateTabProps {
	formData: MediaProfileFormData;
	setFormData: (data: MediaProfileFormData) => void;
}

// Profile editor tab for the safety template, with read-only tables showing what the
// chosen template allows. Validation and the quality rules apply under every template.
export default function SafetyTemplateTab({
	formData,
	setFormData,
}: SafetyTemplateTabProps) {
	const template = formData.safety_template;

	const { data: description } = useQuery({
		queryKey: ["safety-templates"],
		queryFn: async () => {
			const response = await api.get("/trusted-uploaders/templates");
			return response.data as TemplateDescription;
		},
	});

	const { data: trustedList } = useQuery({
		queryKey: ["trusted-uploaders"],
		queryFn: async () => {
			const response = await api.get("/trusted-uploaders/");
			return response.data as TrustedUploader[];
		},
	});

	const siteAllowed = (site: TemplateSite) =>
		template === "open" ||
		(template === "balanced" && site.tier === "balanced");
	const enabledNames = (trustedList || [])
		.filter((u) => u.enabled)
		.map((u) => u.display_name);

	return (
		<div className="space-y-6">
			<div className="bg-blue-500/20 border border-blue-500/30 rounded-lg p-4 mb-4">
				<h4 className="font-semibold text-sm mb-2">Safety Template</h4>
				<p className="text-xs text-muted-foreground">
					Chooses which releases this profile may download, by the
					site a torrent is listed on and whether its uploader is
					trusted. Torrent validation and the quality rules apply
					under every template.
				</p>
			</div>

			<div className="grid grid-cols-1 md:grid-cols-3 gap-3">
				{TEMPLATES.map((option) => {
					const Icon = option.icon;
					const selected = template === option.value;
					return (
						<button
							key={option.value}
							type="button"
							onClick={() =>
								setFormData({
									...formData,
									safety_template: option.value,
								})
							}
							className={`p-4 rounded-lg border-2 text-left transition-all cursor-pointer ${
								selected
									? "border-primary bg-primary/10"
									: "border-border hover:border-muted-foreground/50"
							}`}
						>
							<div className="flex items-center gap-2 mb-2">
								<Icon
									className={`w-4 h-4 ${selected ? "text-primary" : "text-muted-foreground"}`}
								/>
								<span
									className={`font-medium text-sm ${selected ? "text-primary" : ""}`}
								>
									{option.label}
								</span>
							</div>
							<p className="text-xs text-muted-foreground">
								{option.description}
							</p>
						</button>
					);
				})}
			</div>

			{template === "open" && (
				<div className="flex items-start gap-2 p-3 rounded-lg border border-border bg-muted/50 text-xs">
					<AlertTriangle className="w-4 h-4 text-warning shrink-0" />
					<span>
						This profile accepts releases from any uploader on any
						site.
					</span>
				</div>
			)}

			<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
				<div className="p-4 rounded-lg border border-border">
					<h3 className="font-semibold text-sm mb-1">
						Allowed Sources
					</h3>
					<p className="text-xs text-muted-foreground mb-3">
						{template === "trusted"
							? "Trusted only checks the uploader, so a trusted uploader is allowed on any of these sites."
							: "Sites a release must be listed on when its uploader is not trusted."}
					</p>
					<div className="space-y-1">
						{(description?.sources || []).map((site) => (
							<div
								key={site.key}
								className="flex items-center justify-between text-sm"
							>
								<span>{site.name}</span>
								<span className="flex items-center gap-2">
									<span className="px-2 py-0.5 bg-muted rounded text-xs">
										{site.tier === "balanced"
											? "Balanced"
											: "Open"}
									</span>
									<span
										className={`text-xs ${
											template === "trusted"
												? "text-muted-foreground"
												: siteAllowed(site)
													? "text-green-500"
													: "text-destructive"
										}`}
									>
										{template === "trusted"
											? "trusted uploaders only"
											: siteAllowed(site)
												? "allowed"
												: "not allowed"}
									</span>
								</span>
							</div>
						))}
					</div>
				</div>

				<div className="p-4 rounded-lg border border-border">
					<h3 className="font-semibold text-sm mb-1">
						Uploader Categories
					</h3>
					<p className="text-xs text-muted-foreground mb-3">
						Uploaders in a trusted category are allowed under
						Trusted and Balanced.
					</p>
					<div className="space-y-1 mb-3">
						{(description?.uploader_categories || []).map(
							(category) => (
								<div
									key={category.key ?? "unverified"}
									className="flex items-center justify-between text-sm"
								>
									<span>{category.name}</span>
									<span
										className={`px-2 py-0.5 rounded text-xs ${
											category.trusted
												? "bg-green-500/20 text-green-500"
												: "bg-muted text-muted-foreground"
										}`}
									>
										{category.trusted
											? "Trusted"
											: "Not trusted"}
									</span>
								</div>
							),
						)}
					</div>
					{enabledNames.length > 0 && (
						<p className="text-xs text-muted-foreground">
							Kinora trusted list: {enabledNames.join(", ")}
						</p>
					)}
					<Link
						href="/settings"
						className="inline-block text-xs text-primary hover:underline mt-2"
					>
						Edit the trusted list in Settings, Trusted Uploaders
					</Link>
				</div>
			</div>
		</div>
	);
}
