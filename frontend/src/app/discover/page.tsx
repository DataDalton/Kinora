"use client";

import { Suspense, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import Link from "next/link";
import Image from "next/image";
import MediaDetailModal from "@/components/MediaDetailModal";
import PageHeader from "@/components/PageHeader";
import DiscoverMusicPanel from "./DiscoverMusicPanel";

interface Media {
	id: number;
	title: string;
	name?: string;
	poster_path: string | null;
	backdrop_path: string | null;
	vote_average: number;
	release_date?: string;
	first_air_date?: string;
	media_type?: string;
	anilist_id?: number;
}

const TABS = [
	{ key: "discover", label: "Discover" },
	{ key: "anime", label: "Anime" },
	{ key: "movies", label: "Movies" },
	{ key: "shows", label: "Shows" },
	{ key: "music", label: "Music" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

const GENRES = [
	{ key: "action", label: "Action" },
	{ key: "comedy", label: "Comedy" },
	{ key: "drama", label: "Drama" },
	{ key: "scifi", label: "Sci-Fi" },
	{ key: "horror", label: "Horror" },
	{ key: "romance", label: "Romance" },
];

function DiscoverPageContent() {
	const router = useRouter();
	const searchParams = useSearchParams();
	const [selectedMedia, setSelectedMedia] = useState<Media | null>(null);
	const [showModal, setShowModal] = useState(false);

	const requestedTab = searchParams.get("tab") as TabKey | null;
	const activeTab: TabKey =
		requestedTab && TABS.some((t) => t.key === requestedTab)
			? requestedTab
			: "discover";

	// The tab lives in the URL so a view can be linked and the back button steps through
	// tabs rather than leaving the page.
	const selectTab = (key: TabKey) => {
		router.replace(
			key === "discover" ? "/discover" : `/discover?tab=${key}`,
			{ scroll: false },
		);
	};

	// Every row is gated on its own tab, so opening the page loads only what is visible
	// instead of every row for every media type at once.
	const useDiscoverQuery = (key: string[], url: string, enabled: boolean) =>
		useQuery({
			queryKey: ["discover", ...key],
			queryFn: async () => {
				const response = await api.get(url);
				return response.data;
			},
			enabled,
		});

	const onDiscover = activeTab === "discover";
	const onAnime = activeTab === "anime";
	const onMovies = activeTab === "movies";
	const onShows = activeTab === "shows";

	const trending = useDiscoverQuery(
		["trending"],
		"/discover/trending",
		onDiscover,
	);
	const popular = useDiscoverQuery(
		["popular"],
		"/discover/popular",
		onDiscover,
	);
	const topRated = useDiscoverQuery(
		["top-rated"],
		"/discover/top-rated",
		onDiscover,
	);
	const upcoming = useDiscoverQuery(
		["upcoming"],
		"/discover/upcoming",
		onDiscover,
	);

	const animeTrending = useDiscoverQuery(
		["trending", "anime"],
		"/discover/trending?media_type=anime",
		onAnime,
	);
	const animePopular = useDiscoverQuery(
		["popular", "anime"],
		"/discover/popular?media_type=anime",
		onAnime,
	);
	const animeTopRated = useDiscoverQuery(
		["top-rated", "anime"],
		"/discover/top-rated?media_type=anime",
		onAnime,
	);
	const animeUpcoming = useDiscoverQuery(
		["upcoming", "anime"],
		"/discover/upcoming?media_type=anime",
		onAnime,
	);

	const movieTrending = useDiscoverQuery(
		["trending", "movie"],
		"/discover/trending?media_type=movie",
		onMovies,
	);
	const moviePopular = useDiscoverQuery(
		["popular", "movie"],
		"/discover/popular?media_type=movie",
		onMovies,
	);
	const movieTopRated = useDiscoverQuery(
		["top-rated", "movie"],
		"/discover/top-rated?media_type=movie",
		onMovies,
	);
	const movieUpcoming = useDiscoverQuery(
		["upcoming", "movie"],
		"/discover/upcoming?media_type=movie",
		onMovies,
	);

	const showTrending = useDiscoverQuery(
		["trending", "show"],
		"/discover/trending?media_type=show",
		onShows,
	);
	const showPopular = useDiscoverQuery(
		["popular", "show"],
		"/discover/popular?media_type=show",
		onShows,
	);
	const showTopRated = useDiscoverQuery(
		["top-rated", "show"],
		"/discover/top-rated?media_type=show",
		onShows,
	);

	// Declared individually rather than mapped, so the hook call order stays fixed.
	const actionGenre = useDiscoverQuery(
		["genre", "action"],
		"/discover/genre?genre=action",
		onDiscover,
	);
	const comedyGenre = useDiscoverQuery(
		["genre", "comedy"],
		"/discover/genre?genre=comedy",
		onDiscover,
	);
	const dramaGenre = useDiscoverQuery(
		["genre", "drama"],
		"/discover/genre?genre=drama",
		onDiscover,
	);
	const scifiGenre = useDiscoverQuery(
		["genre", "scifi"],
		"/discover/genre?genre=scifi",
		onDiscover,
	);
	const horrorGenre = useDiscoverQuery(
		["genre", "horror"],
		"/discover/genre?genre=horror",
		onDiscover,
	);
	const romanceGenre = useDiscoverQuery(
		["genre", "romance"],
		"/discover/genre?genre=romance",
		onDiscover,
	);

	const genreQueries = [
		{ ...GENRES[0], query: actionGenre },
		{ ...GENRES[1], query: comedyGenre },
		{ ...GENRES[2], query: dramaGenre },
		{ ...GENRES[3], query: scifiGenre },
		{ ...GENRES[4], query: horrorGenre },
		{ ...GENRES[5], query: romanceGenre },
	];

	const getPosterUrl = (path: string | null, isAnime: boolean = false) => {
		if (!path) return "/placeholder-poster.svg";
		if (isAnime) return path;
		return `https://image.tmdb.org/t/p/w500${path}`;
	};

	const getTitle = (item: Media) => item.title || item.name || "Unknown";

	const getYear = (item: Media) => {
		const date = item.release_date || item.first_air_date;
		return date ? new Date(date).getFullYear() : "";
	};

	const renderGenreCard = (genre: string, genreData: any, title: string) => {
		const posters =
			genreData?.results?.slice(0, 4).map((item: Media) => {
				const isAnime = item.media_type === "anime";
				return getPosterUrl(item.poster_path, isAnime);
			}) || [];

		return (
			<Link
				key={genre}
				href={`/discover/${genre}`}
				className="relative rounded-lg overflow-hidden aspect-3/2 group hover:shadow-xl transition transform hover:scale-105"
			>
				<div className="absolute inset-0 grid grid-cols-2 grid-rows-2 gap-1">
					{posters.map((poster: string, idx: number) => (
						<div
							key={idx}
							className="bg-cover bg-center"
							style={{ backgroundImage: `url(${poster})` }}
						/>
					))}
					{posters.length === 0 && (
						<div className="col-span-2 row-span-2 bg-linear-to-br from-gray-700 to-gray-900" />
					)}
				</div>
				<div className="absolute inset-0 bg-linear-to-t from-black/90 via-black/50 to-transparent" />
				<div className="absolute bottom-0 left-0 right-0 p-4">
					<h3 className="text-xl font-bold text-white">{title}</h3>
				</div>
			</Link>
		);
	};

	const renderMediaGrid = (
		items: Media[],
		title: string,
		loading: boolean,
	) => (
		<div className="mb-12">
			<h2 className="text-2xl font-bold mb-4">{title}</h2>
			{loading ? (
				<div className="text-center py-12">Loading...</div>
			) : items && items.length > 0 ? (
				<div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
					{items.slice(0, 12).map((item) => {
						const isAnime = item.media_type === "anime";
						return (
							<div
								key={`${item.media_type}-${item.id}`}
								onClick={() => {
									setSelectedMedia(item);
									setShowModal(true);
								}}
								className="bg-card text-card-foreground rounded-lg shadow overflow-hidden hover:shadow-lg transition cursor-pointer"
							>
								<div className="relative aspect-2/3">
									<Image
										src={getPosterUrl(
											item.poster_path,
											isAnime,
										)}
										alt={getTitle(item)}
										fill
										sizes="(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 20vw"
										className="object-cover"
									/>
								</div>
								<div className="p-3">
									<h3
										className="font-semibold text-sm truncate"
										title={getTitle(item)}
									>
										{getTitle(item)}
									</h3>
									<div className="flex justify-between items-center mt-2">
										<span className="text-xs text-muted-foreground">
											{getYear(item)}
										</span>
										{item.vote_average > 0 && (
											<div className="flex items-center text-xs">
												<svg
													className="w-4 h-4 text-yellow-400 mr-1"
													fill="currentColor"
													viewBox="0 0 20 20"
												>
													<path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
												</svg>
												{item.vote_average.toFixed(1)}
											</div>
										)}
									</div>
								</div>
							</div>
						);
					})}
				</div>
			) : (
				<div className="text-center py-12 text-muted-foreground">
					No content available
				</div>
			)}
		</div>
	);

	return (
		<div className="min-h-screen">
			<PageHeader
				title="Discover"
				description="Explore trending and popular content across all categories"
				gradientFrom="cyan-600/10"
				gradientVia="blue-600/10"
				gradientTo="indigo-600/10"
			/>

			<div className="container mx-auto px-6 pt-6">
				<div className="flex gap-1 border-b border-border">
					{TABS.map((tab) => {
						const active = activeTab === tab.key;
						return (
							<button
								key={tab.key}
								onClick={() => selectTab(tab.key)}
								className={`relative flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 -mb-px transition cursor-pointer ${
									active
										? "border-primary text-foreground"
										: "border-transparent text-muted-foreground hover:text-foreground hover:border-border"
								}`}
							>
								{tab.label}
							</button>
						);
					})}
				</div>
			</div>

			<div className="container mx-auto px-6 py-8">
				{activeTab === "discover" && (
					<>
						<div className="mb-12">
							<h2 className="text-2xl font-bold mb-4">
								Browse by Category
							</h2>
							<div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-4">
								{genreQueries.map((genre) =>
									renderGenreCard(
										genre.key,
										genre.query.data,
										genre.label,
									),
								)}
							</div>
						</div>

						{renderMediaGrid(
							trending.data?.results || [],
							"Trending Now",
							trending.isLoading,
						)}
						{renderMediaGrid(
							popular.data?.results || [],
							"Popular Across All Media",
							popular.isLoading,
						)}
						{renderMediaGrid(
							topRated.data?.results || [],
							"Top Rated",
							topRated.isLoading,
						)}
						{renderMediaGrid(
							upcoming.data?.results || [],
							"Upcoming Movies",
							upcoming.isLoading,
						)}
					</>
				)}

				{activeTab === "anime" && (
					<>
						{renderMediaGrid(
							animeTrending.data?.results || [],
							"Trending Anime",
							animeTrending.isLoading,
						)}
						{renderMediaGrid(
							animePopular.data?.results || [],
							"Popular Anime",
							animePopular.isLoading,
						)}
						{renderMediaGrid(
							animeTopRated.data?.results || [],
							"Top Rated Anime",
							animeTopRated.isLoading,
						)}
						{renderMediaGrid(
							animeUpcoming.data?.results || [],
							"Upcoming Anime",
							animeUpcoming.isLoading,
						)}
					</>
				)}

				{activeTab === "movies" && (
					<>
						{renderMediaGrid(
							movieTrending.data?.results || [],
							"Trending Movies",
							movieTrending.isLoading,
						)}
						{renderMediaGrid(
							moviePopular.data?.results || [],
							"Popular Movies",
							moviePopular.isLoading,
						)}
						{renderMediaGrid(
							movieTopRated.data?.results || [],
							"Top Rated Movies",
							movieTopRated.isLoading,
						)}
						{renderMediaGrid(
							movieUpcoming.data?.results || [],
							"Upcoming Movies",
							movieUpcoming.isLoading,
						)}
					</>
				)}

				{activeTab === "shows" && (
					<>
						{renderMediaGrid(
							showTrending.data?.results || [],
							"Trending TV Shows",
							showTrending.isLoading,
						)}
						{renderMediaGrid(
							showPopular.data?.results || [],
							"Popular TV Shows",
							showPopular.isLoading,
						)}
						{renderMediaGrid(
							showTopRated.data?.results || [],
							"Top Rated TV Shows",
							showTopRated.isLoading,
						)}
					</>
				)}

				{activeTab === "music" && <DiscoverMusicPanel />}
			</div>

			<MediaDetailModal
				media={selectedMedia}
				isOpen={showModal}
				onClose={() => {
					setShowModal(false);
					setSelectedMedia(null);
				}}
			/>
		</div>
	);
}

export default function DiscoverPage() {
	// useSearchParams requires a suspense boundary during prerendering.
	return (
		<Suspense fallback={<div className="min-h-screen" />}>
			<DiscoverPageContent />
		</Suspense>
	);
}
