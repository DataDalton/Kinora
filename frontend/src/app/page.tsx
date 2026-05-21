"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import Link from "next/link";
import Image from "next/image";
import PageHeader from "@/components/PageHeader";
import { Film, Tv, Sparkles, Music2 } from "lucide-react";

interface RecentItem {
	id: number;
	title: string;
	poster_path: string | null;
	cover_xl?: string | null;
	picture_xl?: string | null;
	created_at: string;
	mediaType: "movie" | "show" | "anime" | "album";
}

export default function HomePage() {
	const { data: stats } = useQuery({
		queryKey: ["stats"],
		queryFn: async () => {
			try {
				const [movies, shows, anime, artists] = await Promise.all([
					api.get("/movies", { params: { limit: 1 } }),
					api.get("/shows", { params: { limit: 1 } }),
					api.get("/anime", { params: { limit: 1 } }),
					api.get("/music/artists").catch(() => ({ data: [] })),
				]);

				return {
					moviesCount:
						movies.data.total || movies.data.movies?.length || 0,
					showsCount:
						shows.data.total || shows.data.shows?.length || 0,
					animeCount:
						anime.data.total || anime.data.anime?.length || 0,
					musicCount: artists.data?.length || 0,
				};
			} catch (error) {
				return {
					moviesCount: 0,
					showsCount: 0,
					animeCount: 0,
					musicCount: 0,
				};
			}
		},
	});

	const { data: recentItems } = useQuery({
		queryKey: ["recent-all"],
		queryFn: async () => {
			try {
				const [movies, shows, anime, albums] = await Promise.all([
					api
						.get("/movies", { params: { limit: 6, page: 1 } })
						.catch(() => ({ data: { movies: [] } })),
					api
						.get("/shows", { params: { limit: 6, page: 1 } })
						.catch(() => ({ data: { shows: [] } })),
					api
						.get("/anime", { params: { limit: 6, page: 1 } })
						.catch(() => ({ data: { anime: [] } })),
					api.get("/music/albums").catch(() => ({ data: [] })),
				]);

				const allItems: RecentItem[] = [
					...(movies.data.movies || []).map((m: any) => ({
						...m,
						mediaType: "movie" as const,
					})),
					...(shows.data.shows || []).map((s: any) => ({
						...s,
						mediaType: "show" as const,
					})),
					...(anime.data.anime || []).map((a: any) => ({
						...a,
						mediaType: "anime" as const,
					})),
					...(albums.data || []).map((a: any) => ({
						...a,
						title: a.title || a.name,
						mediaType: "album" as const,
					})),
				];

				// Sort by created_at descending and take first 12
				return allItems
					.sort(
						(a, b) =>
							new Date(b.created_at).getTime() -
							new Date(a.created_at).getTime(),
					)
					.slice(0, 12);
			} catch (error) {
				return [];
			}
		},
	});

	const getPosterUrl = (item: RecentItem) => {
		if (item.mediaType === "album") {
			return (
				item.cover_xl || item.picture_xl || "/placeholder-poster.svg"
			);
		}
		if (!item.poster_path) return "/placeholder-poster.svg";
		if (item.mediaType === "anime") {
			return item.poster_path;
		}
		return `https://image.tmdb.org/t/p/w500${item.poster_path}`;
	};

	const getMediaIcon = (mediaType: string) => {
		switch (mediaType) {
			case "movie":
				return <Film className="w-3 h-3" />;
			case "show":
				return <Tv className="w-3 h-3" />;
			case "anime":
				return <Sparkles className="w-3 h-3" />;
			case "album":
				return <Music2 className="w-3 h-3" />;
			default:
				return null;
		}
	};

	const getMediaLink = (item: RecentItem) => {
		switch (item.mediaType) {
			case "movie":
				return `/movies/${item.id}`;
			case "show":
				return `/shows/${item.id}`;
			case "anime":
				return `/anime/${item.id}`;
			case "album":
				return `/music/albums/${item.id}`;
			default:
				return "#";
		}
	};

	return (
		<div className="min-h-screen">
			<PageHeader
				title="Dashboard"
				description="Overview of your media library"
				gradientFrom="indigo-600/10"
				gradientVia="purple-600/10"
				gradientTo="pink-600/10"
			/>

			{/* Content Section */}
			<div className="container mx-auto px-6 py-8">
				<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
					<Link
						href="/movies"
						className="bg-card text-card-foreground rounded-lg shadow border-2 border-border p-6 hover:shadow-lg hover:border-primary/50 transition"
					>
						<div className="flex items-center justify-between">
							<div>
								<p className="text-muted-foreground text-sm">
									Movies
								</p>
								<p className="text-3xl font-bold">
									{stats?.moviesCount || 0}
								</p>
							</div>
							<Film className="w-10 h-10 text-muted-foreground" />
						</div>
					</Link>

					<Link
						href="/shows"
						className="bg-card text-card-foreground rounded-lg shadow border-2 border-border p-6 hover:shadow-lg hover:border-primary/50 transition"
					>
						<div className="flex items-center justify-between">
							<div>
								<p className="text-muted-foreground text-sm">
									TV Shows
								</p>
								<p className="text-3xl font-bold">
									{stats?.showsCount || 0}
								</p>
							</div>
							<Tv className="w-10 h-10 text-muted-foreground" />
						</div>
					</Link>

					<Link
						href="/anime"
						className="bg-card text-card-foreground rounded-lg shadow border-2 border-border p-6 hover:shadow-lg hover:border-primary/50 transition"
					>
						<div className="flex items-center justify-between">
							<div>
								<p className="text-muted-foreground text-sm">
									Anime
								</p>
								<p className="text-3xl font-bold">
									{stats?.animeCount || 0}
								</p>
							</div>
							<Sparkles className="w-10 h-10 text-muted-foreground" />
						</div>
					</Link>

					<Link
						href="/music"
						className="bg-card text-card-foreground rounded-lg shadow border-2 border-border p-6 hover:shadow-lg hover:border-primary/50 transition"
					>
						<div className="flex items-center justify-between">
							<div>
								<p className="text-muted-foreground text-sm">
									Music
								</p>
								<p className="text-3xl font-bold">
									{stats?.musicCount || 0}
								</p>
							</div>
							<Music2 className="w-10 h-10 text-muted-foreground" />
						</div>
					</Link>
				</div>

				{recentItems && recentItems.length > 0 && (
					<div className="bg-card text-card-foreground rounded-lg shadow border-2 border-border p-6">
						<h2 className="text-2xl font-bold mb-4">
							Recently Added
						</h2>
						<div className="grid grid-cols-2 md:grid-cols-6 gap-4">
							{recentItems.map((item) => (
								<Link
									key={`${item.mediaType}-${item.id}`}
									href={getMediaLink(item)}
									className="bg-card/50 rounded-lg overflow-hidden border border-border hover:shadow-lg hover:border-primary/50 transition"
								>
									<div className="relative aspect-2/3">
										<Image
											src={getPosterUrl(item)}
											alt={item.title}
											fill
											sizes="(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 20vw"
											className="object-cover"
										/>
										<div className="absolute top-2 left-2 px-1.5 py-0.5 bg-background/80 rounded text-xs flex items-center gap-1">
											{getMediaIcon(item.mediaType)}
										</div>
									</div>
									<div className="p-2">
										<p className="text-sm font-medium truncate">
											{item.title}
										</p>
									</div>
								</Link>
							))}
						</div>
					</div>
				)}

				{(!recentItems || recentItems.length === 0) && (
					<div className="bg-card text-card-foreground rounded-lg shadow border-2 border-border p-12 text-center">
						<h2 className="text-2xl font-bold mb-4">
							Welcome to Kinora!
						</h2>
						<p className="text-muted-foreground mb-6">
							Start by adding movies, TV shows, or anime to your
							library
						</p>
						<div className="flex justify-center gap-4">
							<Link
								href="/search"
								className="px-6 py-3 bg-primary text-primary-foreground rounded hover:opacity-90"
							>
								Add Media
							</Link>
							<Link
								href="/discover"
								className="px-6 py-3 bg-secondary text-secondary-foreground rounded hover:opacity-90"
							>
								Discover Content
							</Link>
						</div>
					</div>
				)}
			</div>
		</div>
	);
}
