"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Globe, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { useToast } from "@/components/toast/ToastProvider";

interface ReleaseRegionCountry {
	code: string;
	name: string;
}

interface ReleaseRegionConfig {
	region: string;
	countries: ReleaseRegionCountry[];
}

const QUERY_KEY = ["release-region"];

// Country whose TMDB release dates the calendar and movie pages use. Saving it
// recomputes the stored dates of every movie in the background.
export default function ReleaseRegionSetting() {
	const toast = useToast();
	const queryClient = useQueryClient();

	const { data, isLoading } = useQuery<ReleaseRegionConfig>({
		queryKey: QUERY_KEY,
		queryFn: async () =>
			(await api.get("/settings/release-region/config")).data,
	});

	const saveMutation = useMutation({
		mutationFn: async (region: string) =>
			(await api.put("/settings/release-region/config", { region })).data,
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: QUERY_KEY });
			queryClient.invalidateQueries({ queryKey: ["calendar"] });
			toast.success("Release dates country saved", {
				description:
					"Movie release dates are being updated for the new country.",
			});
		},
		onError: (error: any) => {
			toast.error("Couldn't save the release dates country", {
				description: error.response?.data?.detail,
			});
		},
	});

	const countries = data?.countries ?? [];
	const region = data?.region ?? "US";
	// Keeps the current value selectable when the TMDB country list could not be loaded.
	const options = countries.some((country) => country.code === region)
		? countries
		: [{ code: region, name: region }, ...countries];

	return (
		<div className="bg-card text-card-foreground border-border border rounded-lg p-4 shadow-sm mb-4">
			<h3 className="font-medium text-lg mb-1 flex items-center gap-2">
				<Globe className="w-5 h-5" />
				Release Dates Country
			</h3>
			<p className="text-sm text-muted-foreground mb-3">
				Movies come out on different dates in each country. Kinora uses
				this country&apos;s digital, physical, and theatrical release
				dates on the calendar and movie pages, and falls back to the
				United States when this country has no date.
			</p>
			<div className="flex items-center gap-2">
				<select
					value={region}
					disabled={isLoading || saveMutation.isPending}
					onChange={(e) => saveMutation.mutate(e.target.value)}
					className="px-3 py-2 rounded-lg bg-background border border-border text-sm focus:ring-2 focus:ring-primary focus:outline-none cursor-pointer"
				>
					{options.map((country) => (
						<option key={country.code} value={country.code}>
							{country.name}
						</option>
					))}
				</select>
				{(isLoading || saveMutation.isPending) && (
					<Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
				)}
			</div>
		</div>
	);
}
