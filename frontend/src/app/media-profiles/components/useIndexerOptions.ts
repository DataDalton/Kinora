"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { INDEXERS_BY_TYPE } from "./constants";

type IndexerScope = keyof typeof INDEXERS_BY_TYPE;

interface IndexerName {
	name: string;
}

// Indexers a profile can pick for one media type. Built-in indexers come first,
// followed by user-defined indexers enabled for search that cover the type.
export function useIndexerOptions(scope: IndexerScope): string[] {
	const { data } = useQuery<IndexerName[]>({
		queryKey: ["indexer-names", scope],
		queryFn: async () =>
			(
				await api.get("/indexers/names", {
					params: { media_type: scope },
				})
			).data,
		staleTime: 60_000,
	});
	const builtIn: string[] = INDEXERS_BY_TYPE[scope];
	const custom = (data ?? [])
		.map((indexer) => indexer.name)
		.filter((name) => !builtIn.includes(name));
	return [...builtIn, ...custom];
}
