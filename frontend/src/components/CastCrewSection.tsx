"use client";

import Image from "next/image";
import { useState, useRef } from "react";
import {
	Users,
	ChevronLeft,
	ChevronRight,
	ChevronDown,
	User,
	Clapperboard,
	Mic,
	Pencil,
} from "lucide-react";

interface CastMember {
	id: number;
	name: string;
	character?: string;
	role?: string;
	profile_path?: string | null;
	image?: string | null;
	order?: number;
}

interface CrewMember {
	id: number;
	name: string;
	job: string;
	department?: string;
	profile_path?: string | null;
}

interface AnimeCastMember {
	id: number;
	name: {
		full: string;
	};
	image?: {
		large: string | null;
	};
}

interface AnimeStaffMember {
	id: number;
	name: {
		full: string;
	};
	primaryOccupations?: string[];
}

interface CastCrewSectionProps {
	mediaType: "movie" | "show" | "anime";
	cast?: CastMember[];
	crew?: CrewMember[];
	animeCharacters?: AnimeCastMember[];
	animeStaff?: AnimeStaffMember[];
	tmdbImageBaseUrl?: string;
	// carousel scrolls one row sideways. grid wraps into rows and shows GRID_PREVIEW_COUNT
	// people until expanded.
	layout?: "carousel" | "grid";
}

const TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w185";
// Two rows of the widest grid before "Show all" is needed.
const GRID_PREVIEW_COUNT = 12;

export default function CastCrewSection({
	mediaType,
	cast,
	crew,
	animeCharacters,
	animeStaff,
	tmdbImageBaseUrl = TMDB_IMAGE_BASE,
	layout = "carousel",
}: CastCrewSectionProps) {
	const [activeTab, setActiveTab] = useState<
		"cast" | "crew" | "characters" | "staff"
	>("cast");
	const [showAll, setShowAll] = useState(false);
	const isGrid = layout === "grid";
	const scrollContainerRef = useRef<HTMLDivElement>(null);

	const scroll = (direction: "left" | "right") => {
		if (scrollContainerRef.current) {
			const scrollAmount = 300;
			scrollContainerRef.current.scrollBy({
				left: direction === "left" ? -scrollAmount : scrollAmount,
				behavior: "smooth",
			});
		}
	};

	const directors = crew?.filter((c) => c.job === "Director") || [];
	const writers =
		crew?.filter(
			(c) =>
				c.department === "Writing" ||
				c.job === "Writer" ||
				c.job === "Screenplay",
		) || [];
	const producers =
		crew?.filter(
			(c) => c.job === "Producer" || c.job === "Executive Producer",
		) || [];
	const filteredCrew = [...directors, ...writers, ...producers].slice(0, 20);

	const isAnime = mediaType === "anime";
	const hasCast = cast && cast.length > 0;
	const hasCrew = filteredCrew.length > 0;
	const hasCharacters = animeCharacters && animeCharacters.length > 0;
	const hasStaff = animeStaff && animeStaff.length > 0;

	if (!hasCast && !hasCrew && !hasCharacters && !hasStaff) {
		return null;
	}

	const tabs = isAnime
		? [
				{
					id: "characters" as const,
					label: "Characters",
					available: hasCharacters,
				},
				{ id: "staff" as const, label: "Staff", available: hasStaff },
			]
		: [
				{ id: "cast" as const, label: "Cast", available: hasCast },
				{ id: "crew" as const, label: "Crew", available: hasCrew },
			];

	const availableTabs = tabs.filter((t) => t.available);

	if (availableTabs.length === 0) {
		return null;
	}

	const defaultTab = availableTabs[0].id;
	const currentTab = availableTabs.find((t) => t.id === activeTab)
		? activeTab
		: defaultTab;

	const renderPersonCard = (
		id: number | string,
		name: string,
		subtitle: string,
		imagePath: string | null | undefined,
		isAnimeImage: boolean = false,
	) => {
		const imageUrl = isAnimeImage
			? imagePath
			: imagePath
				? `${tmdbImageBaseUrl}${imagePath}`
				: null;

		return (
			<div
				key={id}
				className={`text-center group min-w-0 ${isGrid ? "" : "flex-shrink-0 w-32"}`}
			>
				<div className="w-24 h-24 mx-auto mb-2 rounded-full overflow-hidden bg-muted border-2 border-border group-hover:border-primary transition">
					{imageUrl ? (
						<Image
							src={imageUrl}
							alt={name}
							className="w-full h-full object-cover"
							loading="lazy"
							width={185}
							height={278}
						/>
					) : (
						<div className="w-full h-full flex items-center justify-center">
							<User className="w-10 h-10 text-muted-foreground" />
						</div>
					)}
				</div>
				<p className="font-medium text-sm truncate" title={name}>
					{name}
				</p>
				<p
					className="text-xs text-muted-foreground truncate"
					title={subtitle}
				>
					{subtitle}
				</p>
			</div>
		);
	};

	const renderContent = () => {
		if (currentTab === "cast" && hasCast) {
			return cast!
				.slice(0, isGrid ? cast!.length : 20)
				.map((member) =>
					renderPersonCard(
						member.id,
						member.name,
						member.character || member.role || "",
						member.profile_path || member.image,
					),
				);
		}

		if (currentTab === "crew" && hasCrew) {
			return filteredCrew.map((member, index) =>
				renderPersonCard(
					`${member.id}-${index}`,
					member.name,
					member.job,
					member.profile_path,
				),
			);
		}

		if (currentTab === "characters" && hasCharacters) {
			return animeCharacters!.map((character) =>
				renderPersonCard(
					character.id,
					character.name.full,
					"Character",
					character.image?.large,
					true,
				),
			);
		}

		if (currentTab === "staff" && hasStaff) {
			return animeStaff!.map((staff) =>
				renderPersonCard(
					staff.id,
					staff.name.full,
					staff.primaryOccupations?.join(", ") || "Staff",
					null,
					true,
				),
			);
		}

		return null;
	};

	const people = renderContent() ?? [];
	const hiddenCount = isGrid
		? Math.max(people.length - GRID_PREVIEW_COUNT, 0)
		: 0;
	const shownPeople =
		isGrid && !showAll ? people.slice(0, GRID_PREVIEW_COUNT) : people;
	const showAllLabel =
		currentTab === "crew" || currentTab === "staff"
			? "Show all crew"
			: "Show all cast";

	const getTabIcon = (tabId: string) => {
		switch (tabId) {
			case "cast":
				return <Users className="w-4 h-4" />;
			case "crew":
				return <Clapperboard className="w-4 h-4" />;
			case "characters":
				return <User className="w-4 h-4" />;
			case "staff":
				return <Pencil className="w-4 h-4" />;
			default:
				return null;
		}
	};

	return (
		<div className="bg-muted/30 rounded-lg border border-border p-4">
			<div className="flex items-center justify-between mb-4">
				<div className="flex items-center gap-2">
					{availableTabs.map((tab) => (
						<button
							key={tab.id}
							onClick={() => {
								setActiveTab(tab.id);
								setShowAll(false);
							}}
							className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition cursor-pointer ${
								currentTab === tab.id
									? "bg-primary text-primary-foreground"
									: "bg-muted hover:bg-muted/80 text-muted-foreground"
							}`}
						>
							{getTabIcon(tab.id)}
							{tab.label}
						</button>
					))}
				</div>

				{!isGrid && (
					<div className="flex items-center gap-1">
						<button
							onClick={() => scroll("left")}
							className="p-1.5 hover:bg-muted rounded-lg transition cursor-pointer"
							aria-label="Scroll left"
						>
							<ChevronLeft className="w-5 h-5" />
						</button>
						<button
							onClick={() => scroll("right")}
							className="p-1.5 hover:bg-muted rounded-lg transition cursor-pointer"
							aria-label="Scroll right"
						>
							<ChevronRight className="w-5 h-5" />
						</button>
					</div>
				)}
			</div>

			{isGrid ? (
				<>
					<div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-x-3 gap-y-5">
						{shownPeople}
					</div>
					{hiddenCount > 0 && (
						<div className="flex justify-center mt-4">
							<button
								onClick={() =>
									setShowAll((current) => !current)
								}
								aria-expanded={showAll}
								className="flex items-center gap-1.5 px-3 py-1.5 border border-border rounded-lg text-sm font-medium hover:bg-accent transition cursor-pointer"
							>
								{showAll
									? "Show less"
									: `${showAllLabel} (${people.length})`}
								<ChevronDown
									className={`w-4 h-4 transition-transform ${showAll ? "rotate-180" : ""}`}
								/>
							</button>
						</div>
					)}
				</>
			) : (
				<div
					ref={scrollContainerRef}
					className="flex gap-4 overflow-x-auto pb-2 scrollbar-thin scrollbar-thumb-muted scrollbar-track-transparent"
					style={{ scrollbarWidth: "thin" }}
				>
					{people}
				</div>
			)}
		</div>
	);
}
